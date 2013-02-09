PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE votes (id integer, username string, val int);
CREATE TABLE songlist (id integer primary key autoincrement, filename string, artist string, album string, track int, title string);
DELETE FROM sqlite_sequence;
INSERT INTO "sqlite_sequence" VALUES('songlist',7578);
CREATE UNIQUE INDEX voteidx on votes (id, username);
COMMIT;
