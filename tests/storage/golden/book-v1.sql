BEGIN TRANSACTION;
CREATE TABLE confirmed_coins (
    symbol TEXT PRIMARY KEY NOT NULL,
    confirmed_at TEXT NOT NULL
) STRICT;
INSERT INTO "confirmed_coins" VALUES('PIKA','2026-10-08T18:30:15.123456+00:00');
CREATE TABLE passages (
    place INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    saved_at TEXT NOT NULL
) STRICT;
INSERT INTO "passages" VALUES(1,'sha256:04df1d42cc9f233567f7922e180f7baaa2e1a4e9590b2bde80f0c7fd6764fe5e','2026-10-02T19:05:10.250000+00:00');
INSERT INTO "passages" VALUES(2,'sha256:5bba1dd4d626bd94f9328afa7a66cc140f394c4f6f8c0e4c80bc480846a36da9','2026-10-08T18:30:15.123456+00:00');
CREATE TABLE trades (
    place INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    passage INTEGER NOT NULL REFERENCES passages (place),
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    coin TEXT NOT NULL,
    quantity TEXT NOT NULL,
    price TEXT NOT NULL,
    total TEXT NOT NULL,
    derived TEXT CHECK (derived IN ('quantity', 'price', 'total')),
    fee TEXT NOT NULL,
    fee_coin TEXT NOT NULL,
    occurred TEXT NOT NULL,
    time_precision TEXT NOT NULL CHECK (time_precision IN ('day', 'minute', 'second')),
    time_zone TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    platform TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    exported_at TEXT
) STRICT;
INSERT INTO "trades" VALUES(1,'hand-3f6c1e2a-9b7d-4c58-a1e0-5d2b8f4c7a93',1,'buy','ETH','0.4','2500','1000','quantity','0.5','BNB','2026-10-02','day','Europe/Budapest','10月2日在 OKX 花 1000 刀买了以太，价格 2500，手续费 0.5 BNB','OKX',NULL,'2026-10-02T19:05:10.250000+00:00','2026-10-02T19:05:10.250000+00:00','2026-10-03T07:15:42.000250+00:00');
INSERT INTO "trades" VALUES(2,'hand-8d2a4f61-0c3e-4b9a-8e7f-1a5c6d3b2e08',2,'buy','BTC','0.02','94900','1898','total','2','USDT','2026-10-07T21:40:00+02:00','minute','Europe/Budapest','昨天晚上 9 点 40 在币安买了 0.02 BTC，94900，手续费 2 USDT；21:41:30 又卖了 1000 个 PIKA，0.05 一个，共 50，手续费 0，我觉得要涨','Binance',NULL,'2026-10-08T18:30:15.123456+00:00','2026-10-08T18:30:15.123456+00:00',NULL);
INSERT INTO "trades" VALUES(3,'hand-c41e9b7a-6d2f-4e83-b0a5-9f3c2d8e1b76',2,'sell','PIKA','1000','0.05','50',NULL,'0','USDT','2026-10-07T21:41:30+02:00','second','Europe/Budapest','昨天晚上 9 点 40 在币安买了 0.02 BTC，94900，手续费 2 USDT；21:41:30 又卖了 1000 个 PIKA，0.05 一个，共 50，手续费 0，我觉得要涨',NULL,'我觉得要涨','2026-10-08T18:30:15.123456+00:00','2026-10-08T18:30:15.123456+00:00',NULL);
CREATE INDEX passages_by_fingerprint ON passages (fingerprint);
CREATE INDEX trades_by_passage ON trades (passage);
COMMIT;
