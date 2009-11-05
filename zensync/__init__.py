from zenapi import ZenConnection
from zenapi.snapshots import Group, Photo, PhotoSet
from zenapi.updaters import (AccessUpdater, PhotoSetUpdater, GroupUpdater, 
                             PhotoUpdater)

import os
import re
import operator
from threading import Thread
from . import config_sample
import Queue

def slugify(string):
    string = re.sub('\s+', '_', string)
    string = re.sub('[^\w.-]', '', string)
    return string.strip('_.- ').lower()

class ZenSync(object):
    def logElement(self, relpath, e, op='+'):
        print op, relpath, e.__class__.__name__, e.Title
        
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
        self._nthreads=50
        self._queue = Queue.Queue()
        
        
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
        """Returns a list of valid and supported files
        
        Note that it does NOT first run filterContent"""
        return filter(self.isSupportedFile, fnames)
    
    def groupPhotoSetName(self, group):
        """Decides what to name the photoset containing any photos in a folder
        or group
        
        Warning: DO NOT change this rule after the first time you sync, as it
        will not find your photos and will reupload them all!!"""
        return group.Title#'photos'#group.Title+' Picts'
    
    def sync(self):
        """Begin a sync according to the loaded configuration file"""
        self.zen.Authenticate()
        self._queue.put(SyncFolderThread(self, 
                                         self.zen.LoadGroupHierarchy(),
                                         self.localRoot))

        def worker():
            while True:
                item = self._queue.get()
                item.start()
                item.join()
                self._queue.task_done()
        for i in range(self._nthreads):
            t = Thread(target=worker)
            t.setDaemon(True)
            t.start()
        self._queue.join()

        
class SyncPhotoSetThread(Thread):
    def __init__(self, zs, group, title, relpath, photofiles, **kwargs):
        Thread.__init__(self, **kwargs)
        self.zs = zs
        self.group=group
        self.title=title
        self.relpath=relpath
        self.photofiles=photofiles
        
    def run(self):
        # Get photo album for group
        #title = self.groupPhotoSetName(group)
        ps = self.group.getPhotoSet(self.title)
        if ps is None:
            updater=PhotoSetUpdater(Title=self.title, 
                                    Caption=self.title,
                                    CustomReference=self.relpath+'photos')
                
            ps = self.zs.zen.CreatePhotoset(self.group, photoset_type='Gallery',
                                            updater=updater)
            
            self.zs.zen.UpdatePhotoSetAccess(ps, self.zs.NewPhotoSetAccess)
            self.zs.logElement(self.relpath, ps)
                                         
        try:
            ps = self.zs.zen.LoadPhotoSet(ps)
        except Exception:
            self.zs.logElement(self.relpath, ps, 'Error')
            return
        
        # Add photos
        for f in self.photofiles:
            photo = ps.getPhoto(os.path.basename(f))
            if photo is None:
                t = UploadPhotoThread(self.zs, 
                                      ps,
                                      f, 
                                      self.relpath)
                self.zs._queue.put(t)
        
class UploadPhotoThread(Thread):
    def __init__(self, zs, gallery, filepath, relpath, **kwargs):
        Thread.__init__(self, **kwargs)
        self.zs = zs
        self.gallery = gallery
        self.filepath=filepath
        self.relpath = relpath
        
    def run(self):
        photo = self.zs.zen.upload(self.gallery, self.filepath, 
                                   filenameStripRoot=self.zs.localRoot)
        self.zs.zen.UpdatePhotoAccess(photo, self.zs.NewPhotoAccess)
        self.zs.logElement(self.relpath, photo)
        
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
        # Find photos and folders here
        ls = os.listdir(self.folder)
        ls = self.zs.filterContent(ls)
        ls.sort()
        dnames = [f for f in ls if os.path.isdir(os.path.join(self.folder, f))]
        fnames = [os.path.join(self.folder, f) for f in self.zs.filterFiles(ls)]
        fnames = filter(os.path.isfile, fnames)
        
        if self.relpath == '':
            myrelpath = ''
        else:
            myrelpath = self.relpath+'/'
            
        t = SyncPhotoSetThread(self.zs,
                               self.group, 
                               self.zs.groupPhotoSetName(self.group),
                               myrelpath, 
                               fnames)
        self.zs._queue.put(t)
        
        # Add and recurse folders
        for d in dnames:
            child = self.group.getGroup(d)
            if child is None:
                updater= GroupUpdater(Title=d, Caption=d,
                                      CustomReference=myrelpath+slugify(d))
                try:
                    child = self.zs.zen.CreateGroup(self.group, updater)
                except Exception:
                    self.zs.logElement(self.relpath, self.group,
                                       op='Error with child ' + d)
                    return
                self.zs.zen.UpdateGroupAccess(child, self.zs.NewGroupAccess)
                self.zs.logElement(self.relpath, child)
            t = SyncFolderThread(self.zs,
                                 child,
                                 os.path.join(self.folder, d),
                                 relpath=myrelpath+slugify(d))
            self.zs._queue.put(t)
        #self.zs.logElement(self.relpath, self.group, op='Finished')
    
