"""Load tcapy's bundled sample data into the Docker databases the web UI reads from, so you can try tcapy without
downloading any market data.

Market data:      test/resources/small_test_market_df.parquet -> Arctic/MongoDB ('arctic-dukascopy' store), EURUSD
Trade/order data: test/resources/small_test_{trade,order}_df.csv -> MySQL trade_database.trade / .order

The data covers EURUSD from late April to early June 2017. Existing EURUSD market data and the trade/order tables are
replaced.

Run it in the Jupyter container, from the repository folder:

    docker compose exec jupyter python tcapy_scripts/gen/load_sample_data.py
"""

__author__ = 'eastonleisure'

import os
import time

from tcapy.conf.constants import Constants
from tcapy.data.databasesource import DatabaseSourceArctic, DatabaseSourceMySQL

constants = Constants()
resources = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'test', 'resources')

if __name__ == '__main__':
    t0 = time.time()
    print('Uploading market data to Arctic (arctic-dukascopy)...', flush=True)
    arctic = DatabaseSourceArctic(postfix='dukascopy')
    arctic.convert_csv_to_table(os.path.join(resources, 'small_test_market_df.parquet'), 'EURUSD',
                                constants.arctic_market_data_database_table,
                                if_exists_table='replace', if_exists_ticker='replace',
                                market_trade_data='market', remove_duplicates=False)
    print('  done in %.1fs' % (time.time() - t0), flush=True)

    mapping = constants.mysql_trade_order_mapping
    csvs = {'trade_df': 'small_test_trade_df.csv', 'order_df': 'small_test_order_df.csv'}
    mysql = DatabaseSourceMySQL()

    for k, csv in csvs.items():
        t0 = time.time()
        print('Uploading %s -> MySQL %s...' % (csv, mapping[k]), flush=True)
        mysql.convert_csv_to_table(os.path.join(resources, csv), None, mapping[k],
                                   database_name=constants.mysql_trade_data_database_name,
                                   if_exists_table='replace', market_trade_data='trade')
        print('  done in %.1fs' % (time.time() - t0), flush=True)

    # Read back to check
    mkt = arctic.fetch_market_data(start_date='25 Apr 2017', finish_date='05 Jun 2017', ticker='EURUSD',
                                   table_name=constants.arctic_market_data_database_table)
    print('\nArctic EURUSD rows: %d (%s -> %s)' % (len(mkt), mkt.index.min(), mkt.index.max()))

    for k in csvs:
        df = mysql.fetch_trade_order_data(start_date='25 Apr 2017', finish_date='05 Jun 2017', ticker='EURUSD',
                                          table_name=mapping[k], database_name=constants.mysql_trade_data_database_name)
        print('MySQL %s EURUSD rows: %d' % (mapping[k], len(df)))

    print('\nDone. In the web UI (http://localhost:9500/tcapy/), pick EURUSD and dates between 2017-04-26 and 2017-06-02.')
