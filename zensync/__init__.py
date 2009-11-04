from zenapi import ZenConnection
from zenapi.snapshots import Group, Photo, PhotoSet
from zenapi.updaters import (AccessUpdater, PhotoSetUpdater, GroupUpdater, 
                             PhotoUpdater)

import os
import re
import operator
import threading
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
        
    
    class _threadcaller(threading.Thread):
        def __init__(self, method, args, **kwargs):
            threading.Thread.__init__(self, **kwargs)
            if not operator.isSequenceType(args):
                args = ((args,), {})
            self.setargs(method, args[0], args[1])
            
        def setargs(self, method, methodargs, methodkwds):
            self._response=None
            self._method=method
            self._methodargs = methodargs
            self._methodkwds = methodkwds
            
        def run(self):
            self._response=self._method(*self._methodargs, **self._methodkwds)
        
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
    
    def photoUploadThread(self, gallery, filepath, myrelpath):
        def f():
            photo = self.zen.upload(gallery, filepath, 
                                    filenameStripRoot=self.localRoot)
            self.zen.UpdatePhotoAccess(photo, self.NewPhotoAccess)
            self.logAddElement(myrelpath, photo)
        t = threading.Thread(target=f)
        t.start()
        return t
    
    def syncFolder(self, group, folder, relpath=''):
        """The business end.  No need to call directly, is designed for 
        recursive directory-tree walking
        
        :Parameters:
          group: Group snapshot representing the parent group
          folder: absolute path to a folder on your hard drive, which will be
            synced with group
          relpath: relative path to the localRoot or root gallery
        """
          
        threads=[]
        
        # Find photos and folders here
        ls = os.listdir(folder)
        dnames = self.filterContent([f for f in ls if os.path.isdir(os.path.join(folder, f))])
        fnames = self.filterFiles([f for f in ls if os.path.isfile(os.path.join(folder, f))])
        if relpath == '':
            myrelpath = ''
        else:
            myrelpath = relpath+'/'
            
        # Get photo album for group
        title = self.groupPhotoSetName(group)
        ps = group.getPhotoSet(title)
        if ps is None:
            updater=PhotoSetUpdater(Title=title, 
                                    Caption=title,
                                    CustomReference=myrelpath+'photos')

                
            ps = self.zen.CreatePhotoset(group, photoset_type='Gallery',
                                         updater=updater)
            self.zen.UpdatePhotoSetAccess(ps, self.NewPhotoSetAccess)
            self.logAddElement(myrelpath, ps)
                                         
        ps = self.zen.LoadPhotoSet(ps)
        
        # Add photos
        for f in fnames:
            photo = ps.getPhoto(f)
            if photo is None:
                threads.append(self.photoUploadThread(ps,
                                                      os.path.join(folder, f), 
                                                      myrelpath))
            
        # Add and recurse folders
        for d in dnames:
            child = group.getGroup(d)
            if child is None:
                child = self.zen.CreateGroup(group, 
                                             GroupUpdater(Title=d,
                                                          Caption=d,
                                                          CustomReference=myrelpath+slugify(d)))
                self.zen.UpdateGroupAccess(child, self.NewGroupAccess)
                self.logAddElement(myrelpath, child)
            t = self._threadcaller(self.syncFolder, ((child, 
                                                      os.path.join(folder, d),
                                                      ), 
                                                     dict(relpath=myrelpath+slugify(d))))
            t.start()
            threads.append(t)
        [t.join() for t in threads]
        del threads
    
    def sync(self):
        """Begin a sync according to the loaded configuration file"""
        self.zen.Authenticate()
        self.syncFolder(self.zen.LoadGroupHierarchy(), self.localRoot)
        
