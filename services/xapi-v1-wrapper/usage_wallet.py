#!/usr/bin/env python3
"""NW-API stage 9-10 usage ledger and shadow wallet helpers."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ChargeEstimate:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_usd_micros: int = 0
    output_usd_micros: int = 0
    total_usd_micros: int = 0


def init_usage_wallet_schema(db_path: str) -> None:
    con = sqlite3.connect(db_path, timeout=10)
    try:
        con.executescript('''
CREATE TABLE IF NOT EXISTS nw_wallets(user_id INTEGER PRIMARY KEY,balance_usd_micros INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nw_usage_events(id INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT NOT NULL UNIQUE,user_id INTEGER NOT NULL,key_id INTEGER,key_source TEXT NOT NULL DEFAULT 'nw',provider TEXT NOT NULL DEFAULT 'sub2api',method TEXT NOT NULL,path TEXT NOT NULL,model TEXT,status TEXT NOT NULL,http_status INTEGER NOT NULL DEFAULT 0,prompt_tokens INTEGER NOT NULL DEFAULT 0,completion_tokens INTEGER NOT NULL DEFAULT 0,total_tokens INTEGER NOT NULL DEFAULT 0,input_usd_micros INTEGER NOT NULL DEFAULT 0,output_usd_micros INTEGER NOT NULL DEFAULT 0,total_usd_micros INTEGER NOT NULL DEFAULT 0,usage_status TEXT NOT NULL DEFAULT 'no_usage',raw_usage_json TEXT,latency_ms INTEGER NOT NULL DEFAULT 0,error_code TEXT,created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_nw_usage_events_user_created ON nw_usage_events(user_id,created_at);
CREATE INDEX IF NOT EXISTS idx_nw_usage_events_key ON nw_usage_events(key_id,created_at);
CREATE TABLE IF NOT EXISTS nw_wallet_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,usage_event_id INTEGER,request_id TEXT,kind TEXT NOT NULL,amount_usd_micros INTEGER NOT NULL,balance_after_usd_micros INTEGER NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,note TEXT,created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_nw_wallet_ledger_user_created ON nw_wallet_ledger(user_id,created_at);
CREATE TABLE IF NOT EXISTS nw_providers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,kind TEXT NOT NULL DEFAULT 'openai_compatible',base_url TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',priority INTEGER NOT NULL DEFAULT 100,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS nw_provider_models(id INTEGER PRIMARY KEY AUTOINCREMENT,public_model TEXT NOT NULL,provider_name TEXT NOT NULL,upstream_model TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',created_at INTEGER NOT NULL,UNIQUE(public_model,provider_name));
''')
        now = int(time.time())
        con.execute("INSERT OR IGNORE INTO nw_providers(name,kind,base_url,status,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", ('sub2api','openai_compatible','env:XAPI_UPSTREAM','active',100,now,now))
        con.commit()
    finally:
        con.close()


def usd_per_million_to_micros(tokens: int, price_per_million: float) -> int:
    return int(round((int(tokens or 0) * float(price_per_million or 0) * 1_000_000) / 1_000_000))


def estimate_charge(con: sqlite3.Connection, model: str, prompt_tokens: int, completion_tokens: int) -> ChargeEstimate:
    row = con.execute('SELECT input_price,output_price FROM model_prices WHERE model=?', (model or '',)).fetchone()
    input_price = float(row[0] or 0) if row else 0.0
    output_price = float(row[1] or 0) if row else 0.0
    input_cost = usd_per_million_to_micros(prompt_tokens, input_price)
    output_cost = usd_per_million_to_micros(completion_tokens, output_price)
    return ChargeEstimate(int(prompt_tokens or 0), int(completion_tokens or 0), int((prompt_tokens or 0) + (completion_tokens or 0)), input_cost, output_cost, input_cost + output_cost)


def record_usage_event(db_path: str, *, request_id: str, user_id: int, key_id: int | None, key_source: str, provider: str, method: str, path: str, model: str, http_status: int, usage_status: str, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0, raw_usage_json: str = '', latency_ms: int = 0, error_code: str = '') -> None:
    if not request_id:
        return
    con = sqlite3.connect(db_path, timeout=10)
    try:
        init_usage_wallet_schema(db_path)
        charge = estimate_charge(con, model, prompt_tokens, completion_tokens)
        status = 'billed_shadow' if http_status < 400 and charge.total_usd_micros > 0 else ('no_usage' if http_status < 400 else 'error')
        con.execute('BEGIN IMMEDIATE')
        con.execute('INSERT OR IGNORE INTO nw_wallets(user_id,balance_usd_micros,updated_at) VALUES(?,?,?)', (user_id, 0, int(time.time())))
        con.execute('''INSERT OR IGNORE INTO nw_usage_events(request_id,user_id,key_id,key_source,provider,method,path,model,status,http_status,prompt_tokens,completion_tokens,total_tokens,input_usd_micros,output_usd_micros,total_usd_micros,usage_status,raw_usage_json,latency_ms,error_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (request_id,user_id,key_id,key_source or 'nw',provider or 'sub2api',method,path,model,status,int(http_status or 0),charge.input_tokens,charge.output_tokens,int(total_tokens or charge.total_tokens),charge.input_usd_micros,charge.output_usd_micros,charge.total_usd_micros,usage_status or 'no_usage',raw_usage_json or '',int(latency_ms or 0),error_code or '',int(time.time())))
        ev = con.execute('SELECT id,total_usd_micros FROM nw_usage_events WHERE request_id=?', (request_id,)).fetchone()
        if ev and ev[1] and key_source == 'nw':
            idem = 'usage:' + request_id
            exists = con.execute('SELECT id FROM nw_wallet_ledger WHERE idempotency_key=?', (idem,)).fetchone()
            if not exists:
                bal = con.execute('SELECT balance_usd_micros FROM nw_wallets WHERE user_id=?', (user_id,)).fetchone()[0]
                after = int(bal or 0) - int(ev[1])
                con.execute('UPDATE nw_wallets SET balance_usd_micros=?,updated_at=? WHERE user_id=?', (after,int(time.time()),user_id))
                con.execute('INSERT INTO nw_wallet_ledger(user_id,usage_event_id,request_id,kind,amount_usd_micros,balance_after_usd_micros,idempotency_key,note,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (user_id, ev[0], request_id, 'usage_debit_shadow', -int(ev[1]), after, idem, 'shadow billing debit', int(time.time())))
                con.execute('UPDATE nw_api_keys SET quota_used=quota_used+? WHERE id=?', (int(ev[1]) / 1_000_000.0, key_id))
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
    finally:
        con.close()
