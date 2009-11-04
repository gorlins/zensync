from zenapi import ZenConnection
from zenapi.snapshots import Group, Photo, PhotoSet
from zenapi.updaters import (AccessUpdater, PhotoSetUpdater, GroupUpdater, 
                             PhotoUpdater)

import os
import re
import operator
from threading import Thread
from . import config_sample

def slugify(string):
    string = re.sub('\s+', '_', string)
    string = re.sub('[^\w.-]', '', string)
    return string.strip('_.- ').lower()

class ZenSync(object):
    def logAddElement(self, relpath, e):
        print '+', relpath, e.__class__.__name__, e.Title
        
    def __init__(self, configfile):
        defaults = vars(config_sample)
        config = dict()
        try:
            execfile(configfile, config)
            
            for k in [v for v in defaults if not v.startswith('__')]:
                setattr(self, k, config.get(k, defaults[k]))
                
            self.zen = ZenConnection(username=self.USERNAME,
                                     password=self.PASSWORD)
            self.NewGroupAccess = AccessUpdater(self.NewGroupAccess)
            self.NewPhotoSetAccess = AccessUpdater(self.NewPhotoSetAccess)
            self.NewPhotoAccess = AccessUpdater(self.NewPhotoAccess)
        
        except Exception, e:
            print "Couldn't parse config file!!"
            raise e
        
    def isValid(self, name):
        """Returns True if a file or folder name should be synced"""
        return not (any([name.lower().startswith(s.lower()) 
                         for s in self.ExcludeStartsWith]))
    
    def isSupportedFile(self, f):
        """Returns True if a filename represents a valid filetype"""
        (n, ext) = os.path.splitext(f)
        return ext[1:].lower() in [v.lower() for v in self.ValidFileTypes]
    
    def filterContent(self, names):
        """Returns a list of only the valid (to be synced) file/folder names"""
        return filter(self.isValid, names)
    
    def filterFiles(self, fnames):
        """Returns a list of valid and supported files"""
        return filter(self.isSupportedFile, self.filterContent(fnames))
    
    def groupPhotoSetName(self, group):
        """Decides what to name the photoset containing any photos in a folder
        or group
        
        Warning: DO NOT change this rule after the first time you sync, as it
        will not find your photos and will reupload them all!!"""
        return group.Title#'photos'#group.Title+' Picts'
    
    def sync(self):
        """Begin a sync according to the loaded configuration file"""
        self.zen.Authenticate()
        t = SyncFolderThread(self, 
                             self.zen.LoadGroupHierarchy(),
                             self.localRoot)
        t.start()
        t.join()
        
class SyncPhotoSetThread(Thread):
    def __init__(self, zs, group, title, relpath, photofiles, **kwargs):
        Thread.__init__(self, **kwargs)
        self.zs = zs
        self.group=group
        self.title=title
        self.relpath=relpath
        self.photofiles=photofiles
        
    def run(self):
        group=self.group
        title=self.title
        relpath=self.relpath
        photofiles=self.photofiles
        
        threads = []
        # Get photo album for group
        #title = self.groupPhotoSetName(group)
        ps = group.getPhotoSet(title)
        if ps is None:
            updater=PhotoSetUpdater(Title=title, 
                                    Caption=title,
                                    CustomReference=relpath+'photos')
                
            ps = self.zs.zen.CreatePhotoset(group, photoset_type='Gallery',
                                            updater=updater)
            
            self.zs.zen.UpdatePhotoSetAccess(ps, self.zs.NewPhotoSetAccess)
            self.zs.logAddElement(relpath, ps)
                                         
        ps = self.zs.zen.LoadPhotoSet(ps)
        
        # Add photos
        for f in photofiles:
            photo = ps.getPhoto(os.path.basename(f))
            if photo is None:
                t = UploadPhotoThread(self.zs, 
                                      ps,
                                      f, 
                                      relpath)
                t.start()
                threads.append(t)
        [t.join() for t in threads]
        del threads
        
class UploadPhotoThread(Thread):
    def __init__(self, zs, gallery, filepath, relpath, **kwargs):
        Thread.__init__(self, **kwargs)
        self.zs = zs
        self.gallery = gallery
        self.filepath=filepath
        self.relpath = relpath
        
    def run(self):
        myrelpath=self.relpath
        gallery=self.gallery
        filepath=self.filepath
        photo = self.zs.zen.upload(gallery, filepath, 
                                   filenameStripRoot=self.zs.localRoot)
        self.zs.zen.UpdatePhotoAccess(photo, self.zs.NewPhotoAccess)
        self.zs.logAddElement(myrelpath, photo)
        
class SyncFolderThread(Thread):
    def __init__(self, zs, group, folder, relpath='', **kwargs):
        """The business end.  No need to call directly, is designed for 
        recursive directory-tree walking
        
        :Parameters:
        group: Group snapshot representing the parent group
        folder: absolute path to a folder on your hard drive, which will be
        synced with group
        relpath: relative path to the localRoot or root gallery
        """
        Thread.__init__(self, **kwargs)
        self.zs=zs
        self.group=group
        self.folder=folder
        self.relpath=relpath
        
    def run(self):
        group=self.group
        folder=self.folder
        relpath=self.relpath
        threads=[]
        # Find photos and folders here
        ls = os.listdir(folder)
        dnames = [f for f in ls if os.path.isdir(os.path.join(folder, f))]
        dnames = self.zs.filterContent(dnames)
        fnames = [f for f in ls if os.path.isfile(os.path.join(folder, f))]
        fnames = self.zs.filterFiles(fnames)
        if relpath == '':
            myrelpath = ''
        else:
            myrelpath = relpath+'/'
            
        t = SyncPhotoSetThread(self.zs,
                               group, 
                               self.zs.groupPhotoSetName(group),
                               myrelpath, 
                               [os.path.join(folder, f) for f in fnames])
        t.start()
        threads.append(t)
        
        # Add and recurse folders
        for d in dnames:
            child = group.getGroup(d)
            if child is None:
                updater= GroupUpdater(Title=d, Caption=d,
                                      CustomReference=myrelpath+slugify(d))
                child = self.zs.zen.CreateGroup(group, updater)
                self.zs.zen.UpdateGroupAccess(child, self.zs.NewGroupAccess)
                self.zs.logAddElement(myrelpath, child)
            t = SyncFolderThread(self.zs,
                                 child,
                                 os.path.join(folder, d),
                                 relpath=myrelpath+slugify(d))
            t.start()
            threads.append(t)
        [t.join() for t in threads]
        del threads
    
