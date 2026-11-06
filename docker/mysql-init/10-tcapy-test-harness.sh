#!/bin/bash
# Runs once, when MySQL initialises an empty data directory (mounted at /docker-entrypoint-initdb.d).
# tcapy's notebooks and test scripts write trade data to trade_database_test_harness, so give MYSQL_USER the same
# rights there as on MYSQL_DATABASE (which the MySQL image grants automatically).
set -e
mysql -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
CREATE DATABASE IF NOT EXISTS trade_database_test_harness;
GRANT ALL PRIVILEGES ON trade_database_test_harness.* TO '$MYSQL_USER'@'%';
FLUSH PRIVILEGES;
SQL
