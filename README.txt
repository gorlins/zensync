Install with python setup.py install

Requires the zenapi package, available from wherever you got this

To sync with Zenfolio, first copy zensync/config_sample.py to a destination of your choice, and rename to something like 'myzensync.py'.  Edit the file to your liking (missing variables will default to those found in the original config_sample)

Create a ZenSync object with your config file, or modify sync.py to point it to your config file.  Then either call python /path/to/sync.py or myZenSyncInstance.sync() from a python script of your choice
