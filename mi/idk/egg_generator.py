#!/usr/bin/env python

"""
@file coi-services/mi.idk/egg_generator.py
@author Bill French
@brief Generate egg for a driver.  This uses snakefood to build
a dependecy list and includes all files in the driver directory.
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import re
import os
import sys
import shutil
import subprocess
from os.path import basename, dirname
from operator import itemgetter
from string import Template

from mi.idk import prompt
from mi.idk.config import Config
from mi.idk.metadata import Metadata
from mi.idk.driver_generator import DriverGenerator
from mi.core.log import get_logger ; log = get_logger()

from mi.idk.exceptions import NotPython
from mi.idk.exceptions import NoRoot
from mi.idk.exceptions import FileNotFound
from mi.idk.exceptions import InvalidParameters
from mi.idk.exceptions import MissingTemplate
from mi.idk.exceptions import ValidationFailure
from mi.idk.exceptions import IDKException
from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.driver_generator import DriverGenerator

from snakefood.util import iter_pyfiles, setup_logging, def_ignores, is_python
from snakefood.depends import output_depends, read_depends
from snakefood.find import find_dependencies
from snakefood.find import find_imports
from snakefood.find import ERROR_IMPORT, ERROR_SYMBOL, ERROR_UNUSED
from snakefood.fallback.collections import defaultdict
from snakefood.roots import *


class DependencyList:
    """
    Build a list of dependency classes for a python module.  This uses the snakefood
    module to build out the list.  This class does not output __init__.py files by
    default, but passing the include_interanl_init option to the constructor can
    change this behavior.
    
    Usage:
    
    deplist = DependencyList(target_file, True)
    
    # All dependency files.
    all_deps = deplist.all_dependencies()
    
    # Internal dependencies
    int_deps = deplist.internal_dependencies()
    
    # External dependencies
    extern_deps = deplist.external_dependencies()
    """
    def __init__(self, filename, include_internal_init = False):
        if not os.path.isfile(filename):
            raise FileNotFound(filename)
            
        if not is_python(filename):
            raise NotPython(filename)
            
        self.include_internal_init = include_internal_init
            
        self.dependency_list = None
        self.file_roots = None
        
        self.filename = filename
        
    def fetch_dependencies(self):
        """
        Fetch all dependencies and follow the target file.
        This was inspired by the snakefood library
        snakefood-1.4-py2.7.egg/snakefood/gendeps.py
        """
        # No need to run this twice
        if self.dependency_list: return self.dependency_list
        
        log.info("Fetching internal dependecies: %s" % self.filename)
        
        depends = find_imports(self.filename, 1, 0)
        
        # Get the list of package roots for our input files and prepend them to the
        # module search path to insure localized imports.
        inroots = find_roots([self.filename], [])
        self.file_roots = inroots
        
        if not inroots:
            raise NoRoot
        
        for file in inroots:
            log.debug("Root found: %s" % file)
        sys.path = inroots + sys.path
            
        #log.debug("Using the following import path to search for modules:")
        #for dn in sys.path:
        #    log.debug(" --  %s" % dn)
        inroots = frozenset(inroots)

        # Find all the dependencies.
        log.debug("Processing file:")
        allfiles = defaultdict(set)
        allerrors = []
        processed_files = set()
        ignorefiles = []
        alldependencies = []

        fiter = iter_pyfiles([self.filename], ignorefiles, False)
        while 1:
            newfiles = set()

            for fn in fiter:
                log.debug("  post-filter: %s" % fn)
                processed_files.add(fn)
    
                if is_python(fn):
                    files, errors = find_dependencies(fn, 0, 0)
                    log.debug("dependency file count: %d" % len(files))
                    allerrors.extend(errors)
                else:
                    # If the file is not a source file, we don't know how to get the
                    # dependencies of that (without importing, which we want to
                    # avoid).
                    files = []
            
                # When packages are the source of dependencies, remove the __init__
                # file.  This is important because the targets also do not include the
                # __init__ (i.e. when "from <package> import <subpackage>" is seen).
                if basename(fn) == '__init__.py':
                    fn = dirname(fn)

                # no dependency.
                from_ = relfile(fn, ignorefiles)
                if from_ is None:
                    log.debug("from_ empty.  Move on")
                    continue
                infrom = from_[0] in inroots
                log.debug( "  from: %s" % from_[0])
                log.debug( "  file: %s" % from_[1])
                allfiles[from_].add((None, None))
    
                # Add the dependencies.
                for dfn in files:
                    xfn = dfn
                    if basename(xfn) == '__init__.py':
                        xfn = dirname(xfn)
        
                    to_ = relfile(xfn, ignorefiles)
                    into = to_[0] in inroots
                    log.debug( "  from: %s,  to: %s" % (from_[1], to_[1]))

                    if dfn in alldependencies:
                        log.trace("Already added %s to dependency list" % dfn)
                    else:
                        log.debug("Add %s to dependency list" % dfn)
                        allfiles[from_].add(to_)
                        newfiles.add(dfn)
                        alldependencies.append(dfn)

                    
            if not newfiles:
                log.debug("No more new files.  all done")
                break
            else:
                fiter = iter(sorted(newfiles))
                
        # Output the list of roots found.
        log.debug("Found roots:")

        found_roots = set()
        for key, files in allfiles.iteritems():
            found_roots.add(key[0])
            found_roots.update(map(itemgetter(0),files))
        if None in found_roots:
            found_roots.remove(None)
        for root in sorted(found_roots):
            log.debug("  %s" % root)

        
        self.dependency_list = allfiles
        return self.dependency_list;
                
        
    def internal_dependencies(self):
        """
        Return a list of internal dependencies for self.filename
        """
        filelist = self.fetch_dependencies()
        
        initlist = []
        if self.include_internal_init:
            initlist = self._init_set(filelist, self.file_roots[0])
            
        log.debug( "Internal dependencies:" )
        return sorted(initlist + self._dependency_set(filelist, True, False))
        
        
    def external_dependencies(self):
        """
        Return a list of external dependencies for self.filename
        """
        filelist = self.fetch_dependencies()
        
        log.debug( "External dependencies:" )
        return self._dependency_set(filelist, False, True)
        
        
    def all_dependencies(self):
        """
        Return all dependencies for self.filename
        """
        filelist = self.fetch_dependencies()
        
        log.debug( "All dependencies:" )
        return self._dependency_set(filelist)
        
        
    def internal_roots(self):
        """
        Return a list of internal dependency roots for self.filename
        """
        filelist = self.fetch_dependencies()
        
        log.debug( "Internal roots:" )
        return self._root_set(filelist, True, False)
        
        
    def external_roots(self):
        """
        Return a list of external dependency roots for self.filename
        """
        filelist = self.fetch_dependencies()
        
        log.debug( "External roots:" )
        return self._root_set(filelist, False, True)
        
        
    def all_roots(self):
        """
        Return all dependency roots for self.filename
        """
        filelist = self.fetch_dependencies()
        
        log.debug( "All roots:" )
        return self._root_set(filelist)
        
        
    def _dependency_set(self, filelist, internal = None, external = None):
        """
        Return a set of files that are in the dependency list.  The internal and external
        flags speficy the list contents.  Internal set returns all files that have the same
        root as the target file.  External is the opposite.
        """
        result = []
        for key, files in filelist.iteritems():
            inroot = key[0] in self.file_roots
            if(not(internal or external) or (internal and inroot) or (external and not inroot)):
                result.append(key[1])
        
        result = sorted(result)
        for file in result:
            log.debug("   %s" % file)
        
        return result
        
    
    def _root_set(self, filelist, internal = None, external = None):
        """
        Return a set of files that are in the dependency list.  The internal and external
        flags speficy the list contents.  Internal set returns all files that have the same
        root as the target file.  External is the opposite.
        """
        result = []
        for key, files in filelist.iteritems():
            inroot = key[0] in self.file_roots
            if(not(internal or external) or (internal and inroot) or (external and not inroot)):
                if not key[0] in result:
                    result.append(key[0])
                
        result = sorted(result)
        for root in result:
            log.debug("   %s" % root)
        
        return result
    
    def _init_set(self, filelist, root):
        """
        Return a set of init files for the filelist passed in.
        """
        #log.debug("Build __init__.py list")
        result = []
        for key, files in filelist.iteritems():
            if key[0] == root:
                for initfile in self._get_init_files(key[1], root):
                    if not initfile in result:
                        result.append(initfile)
        
        result = sorted(result)
        for file in result:
            log.debug(" add init file %s" % file)
        
        return result
    
    def _get_init_files(self, pyfile, root):
        """
        recursively step through a python module path and find all the __init__.py files
        """
        result = []
        current_path = dirname(pyfile);
        while current_path:
            initfile = "%s/__init__.py" % current_path
            abspath = "%s/%s" % (root, initfile)
            log.debug( "  -- Does %s exist?" % abspath )
            if os.path.exists(abspath):
                result.append(initfile)
            current_path = dirname(current_path) 
            
        return result
        

class DriverFileList:
    """
    Build list of files that are associated to a driver.  It uses the DependencyList
    object to get all python files.  Then it will look in the target module directory
    for additional files.
    """
    def __init__(self, metadata, basedir, driver_file = None, driver_test_file = None):
        driver_generator = DriverGenerator(metadata)
        
        self.basedir = basedir

        if driver_file:
            self.driver_file = driver_file
        else:
            self.driver_file = driver_generator.driver_path()

        if driver_test_file:
            self.driver_test_file = driver_test_file
        else:
            self.driver_test_file = driver_generator.driver_test_path()

        self.driver_dependency = None
        self.test_dependency = None
        self.driver_dependency = DependencyList(self.driver_file, include_internal_init=True)
        self.test_dependency = DependencyList(self.driver_test_file, include_internal_init=True)

    def files(self):
        basep = re.compile(self.basedir)
        rootp = re.compile('^/')
        result = []
        
        log.debug( "F: %s" % self.driver_file)
        driver_files = []
        driver_files = self.driver_dependency.internal_dependencies()
        test_files = []
        test_files = self._scrub_test_files(self.test_dependency.internal_dependencies())
        extra_files = []
        extra_files = self._extra_files()
        files = extra_files + driver_files + test_files

        for fn in files:
            if not fn in result:
                f = basep.sub('', fn)
                f = rootp.sub('', f)
                result.append(f)

        log.debug("Result File List: %s" % result)
        return result

    def _scrub_test_files(self, filelist):
        """
        The interface directory is built by generate interfaces so it comes up as an internal dependency.
        """
        # I don't particularly like this, but these generated interface files need to be removed
        result = []
        p = re.compile('^interface\/')
        for file in filelist:
            if p.findall(file):
                log.debug(" Remove: %s" % file)
            else:
                result.append(file)

        return result

    def _extra_files(self):
        result = []
        p = re.compile('\.(py|pyc)$')
        
        for root, dirs, names in os.walk(dirname(self.driver_file)):
            for filename in names:
                # Ignore python files
                if not p.search(filename):
                    result.append("%s/%s" % (root, filename))
                
        return result
    
class EggGenerator:
    """
    Generate driver egg
    """

    def __init__(self, metadata):
        """
        @brief Constructor
        @param metadata IDK Metadata object
        """
        self.metadata = metadata
        self._bdir = None

        if not self._tmp_dir():
            raise InvalidParameters("missing tmp_dir configuration")

        if not self._tmp_dir():
            raise InvalidParameters("missing working_repo configuration")

        self.generator = DriverGenerator(self.metadata)
        test_import = __import__(self._test_module())

    def _test_module(self):
        return self.generator.test_modulename()

    def _driver_module(self):
        test_config = InstrumentDriverTestConfig()
        return test_config.driver_module

    def _driver_class(self):
        test_config = InstrumentDriverTestConfig()
        return test_config.driver_class

    def _repo_dir(self):
        return '/tmp/repoclone/marine-integrations'

    def _tmp_dir(self):
        return Config().get('tmp_dir')

    def _setup_path(self):
        return os.path.join(self._build_dir(), 'setup.py' )

    def _setup_template_path(self):
        return os.path.join(Config().template_dir(), 'setup.tmpl' )

    def _main_path(self):
        return os.path.join(self._versioned_dir(), 'mi/main.py' )

    def _main_template_path(self):
        return os.path.join(Config().template_dir(), 'main.tmpl' )

    def _build_name(self):
        return "%s_%s_%s_%s" % (
                self.metadata.driver_make,
                self.metadata.driver_model,
                self.metadata.driver_name,
                self.metadata.version.replace('.', '_'),
            )

    def _build_dir(self):
        if self._bdir:
            return self._bdir

        self._bdir = self._generate_build_dir()

        log.info( "egg build dir: %s" % self._bdir)
        return self._bdir

    def _generate_build_dir(self):
        build_dir = os.path.join(self._tmp_dir(), self._build_name())
        # clean out an old build if it exists
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        return build_dir

    def _versioned_dir(self):
        return os.path.join(self._build_dir(),
                            self._build_name())

    def _stage_files(self, files):
        """
        Copy files from the original directory into two levels of versioned
        directories within a staging directory, and replace the mi namespace
        with the versioned driver name.mi to account for the new directory
        (only the lower versioned dir is included in the egg)
        @param files - a list of files to copy into the staging directory
        """
        # make two levels of versioned file directories, i.e.
        #     driverA_0_1 (= build_dir)
        #         driverA_0_1 (= versioned_dir)
        # then copy driverA files into the bottom versioned dir
        if not os.path.exists(self._build_dir()):
            os.makedirs(self._build_dir())
        if not os.path.exists(self._versioned_dir()):
            os.makedirs(self._versioned_dir())

        # we need to make sure an init file is in the versioned dir so
        # that find_packages() will look in here
        init_path = self._versioned_dir() + "/__init__.py"
        if not os.path.exists(init_path):
            init_file = open(init_path, "w")
            init_file.close()

        for file in files:
            dest = os.path.join(self._versioned_dir(), file)
            destdir = dirname(dest)
            source = os.path.join(self._repo_dir(), file)

            log.debug(" Copy %s => %s" % (source, dest))
            # make sure the destination directory exists, if it doesn't make it
            if not os.path.exists(destdir):
                os.makedirs(destdir)

            shutil.copy(source, dest)

            # replace mi in the copied files with the versioned driver module.mi
            # this is necessary because the top namespace in the versioned files starts
            # with the versioned driver name directory, not mi
            driver_file = open(dest, "r")
            contents = driver_file.read()
            driver_file.close()
            new_contents = re.sub(r'(^import |^from |\'|= )mi\.|res/config/mi-logging|\'mi\'',
                                  self._mi_replace,
                                  contents,
                                  count=0,
                                  flags=re.MULTILINE)
            driver_file = open(dest, "w")
            driver_file.write(new_contents)
            driver_file.close()

        # need to add mi-logging.yml special because it is not in cloned repo, only in local repository
        milog = "res/config/mi-logging.yml"
        dest = os.path.join(self._versioned_dir(), milog)
        destdir = dirname(dest)
        source = os.path.join(Config().base_dir(), milog)

        log.debug(" Copy %s => %s" % (source, dest))
        # make sure the destination directory exists, if it doesn't make it
        if not os.path.exists(destdir):
            os.makedirs(destdir)

        shutil.copy(source, dest)

    def _mi_replace(self, matchobj):
        """
        This function is used in regex sub to replace mi with the versioned
        driver name followed by mi
        @param matchobj - the match object from re.sub
        """
        if matchobj.group(0) == 'res/config/mi-logging':
            return self._build_name() + '/' + matchobj.group(0)
        elif matchobj.group(0) == '\'mi\'':
            return '\'' + self._build_name() + '.mi\''
        else:
            return matchobj.group(1) + self._build_name() + '.mi.'   

    def _get_template(self, template_file):
        """
        @brief return a string.Template object constructed with the contents of template_file
        @param template_file path to a file that containes a template
        @retval string.Template object
        """
        try:
            infile = open(template_file)
            tmpl_str = infile.read()
            return Template(tmpl_str)
        except IOError:
            raise MissingTemplate(msg="Missing: %s" % template_file)

    def _generate_setup_file(self):
        if not os.path.exists(self._build_dir()):
            os.makedirs(self._build_dir())

        if not os.path.exists(self._build_dir()):
            raise IDKException("failed to create build dir: %s" % self._build_dir())


        setup_file = self._setup_path()
        setup_template = self._get_template(self._setup_template_path())

        log.debug("Create setup.py file: %s" % setup_file )
        log.debug("setup.py template file: %s" % self._setup_template_path())
        log.debug("setup.py template date: %s" % self._setup_template_data())

        ofile = open(setup_file, 'w')
        code = setup_template.substitute(self._setup_template_data())
        ofile.write(code)
        ofile.close()

    def _setup_template_data(self):
        return {
            'name': self._build_name(),
            'version': self.metadata.version,
            'description': 'ooi core driver',
            'author': self.metadata.author,
            'email': self.metadata.email,
            'url': 'http://www.oceanobservatories.org',
            'driver_module': self._driver_module(),
            'driver_class': self._driver_class(),
            'driver_path': self.metadata.driver_path,
        }

    def _generate_main_file(self):
        if not os.path.exists(self._versioned_dir()):
            os.makedirs(self._versioned_dir())

        main_file= self._main_path()
        main_template = self._get_template(self._main_template_path())

        log.debug("Create mi/main.py file: %s" % main_file )
        log.debug("main.py template file: %s" % self._main_template_path())
        log.debug("main.py template date: %s" % self._setup_template_data())

        ofile = open(main_file, 'w')
        code = main_template.substitute(self._setup_template_data())
        ofile.write(code)
        ofile.close()

    def _verify_ready(self):
        """
        verify that we have all the information and are in the correct state to build the egg
        """
        self._verify_python()
        self._verify_metadata()
        self._verify_version()

    def _verify_metadata(self):
        """
        Ensure we have all the metadata we need to build the egg
        """
        pass

    def _verify_version(self, version = None):
        """
        Ensure we have a good version number and that it has not already been packaged and published
        """
        if version == None:
            version = self.metadata.version

        if not version:
            raise ValidationFailure("Driver version required in metadata")

        p = re.compile("^\d+\.\d+\.\d+$")
        if not p.findall("%s" % version):
            raise ValidationFailure("Version format incorrect '%s', should be x.x.x" % version)

    def _verify_python(self):
        """
        Ensure we build with the correct python version
        """
        if sys.version_info < (2, 7) or sys.version_info >= (2, 8):
            raise ValidationFailure("Egg generation required version 2.7 of python")

    def _build_egg(self, files):
        try:
            self._verify_ready()
            self._stage_files(files)
            self._generate_setup_file()
            self._generate_main_file()

            cmd = "cd %s; python setup.py bdist_egg" % self._build_dir()
            log.info("CMD: %s" % cmd)
            os.system(cmd)

            egg_file = "%s/dist/%s-%s-py2.7.egg" % (self._build_dir(),
                                                    self._build_name(),
                                                    self.metadata.version)

            # Remove all pyc files from the egg.  There was a jira case that suggested
            # including the compiled py files caused the drivers to run slower.
            # https://jira.oceanobservatories.org/tasks/browse/OOIION-1167
            cmd = "zip %s -d \*.pyc" % egg_file
            log.info("CMD: %s" % cmd)
            os.system(cmd)

        except ValidationFailure, e:
            log.error("Failed egg verification: %s" % e )
            return None

        log.debug("Egg file created: %s" % egg_file)
        return egg_file

    def save(self):
        driver_file = self.metadata.driver_dir() + '/' + DriverGenerator(self.metadata).driver_filename()
        driver_test_file = self.metadata.driver_dir() + '/test/' + DriverGenerator(self.metadata).driver_test_filename()
        filelist = DriverFileList(self.metadata, self._repo_dir(), driver_file, driver_test_file)
        return self._build_egg(filelist.files())


if __name__ == '__main__':
    pass

