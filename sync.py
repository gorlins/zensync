from zensync import ZenSync
from time import time

CONFIG_FILE='/path/to/config/file.py'

# Simple test usage
zsync = ZenSync(CONFIG_FILE)
t1 = time()
zsync.sync()
print time()-t1