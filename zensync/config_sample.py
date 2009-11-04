""" Configuration file for zensync
Copy this file somewhere on your hard drive as config.py, change values, 
and then call from zensync

Values missing from your config.py will default to those found here
"""

USERNAME = 'user'
PASSWORD = 'password'

# Directory on your hard drive
localRoot = 'C:\MyPictures'

# Group to sync directory with in Zenfolio (None means root group)
zenRoot = None

# If True, will delete files from Zen if not found on hard drive
DeleteMissingZenFiles = False

# If True, will delete files from hard drive if not found on Zen
DeleteMissingLocalFiles = False

# If True, will reupload newer files
ReuploadNewer = True

# Exclude files or folders 
ExcludeStartsWith = ['.', '@', '~', '#']

# Valid filetype extensions
ValidFileTypes = ['jpg', 'jpeg', 'png', 'gif', 'tif', 'tiff']

# Default access properties for newly created groups, photosets, and photos
# These are keywords passed to AccessUpdaters, None or blank keywords result in
# Zenfolio defaults

# I.e., NewGroupAccess = {'AccessType':'Private',
#                         'AccessMask':'NoPublicSearch, NoPrivateSearch'}
NewGroupAccess = {} # These need some OOP work
NewPhotoSetAccess = {}
NewPhotoAccess = {}
