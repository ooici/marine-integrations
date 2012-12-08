#!/usr/bin/env python

"""
@package mi.idk.test.test_git
@file mi.idk/test/test_git.py
@author Bill French
@brief test git
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs,chdir, system
from os import remove
from os.path import exists
import sys

from nose.plugins.attrib import attr
from mock import Mock
import unittest
from mi.core.unit_test import MiUnitTest

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.idk_git import IDKGit

from mi.idk.exceptions import InvalidGitRepo
from mi.idk.exceptions import GitCommandException

REPO = "https://github.com/ooici/marine-integrations.git"

ROOTDIR="/tmp/test_git.idk_test"
# /tmp is a link on OS X
if exists("/private/tmp"):
    ROOTDIR = "/private%s" % ROOTDIR
    

@attr('UNIT', group='mi')
class TestGit(MiUnitTest):
    """
    Test the git for the IDK
    """
    @classmethod
    def setUpClass(cls):
        system("rm -rf %s" % ROOTDIR)
        if not exists(ROOTDIR):
            makedirs(ROOTDIR)

        idk_git = IDKGit(ROOTDIR)
        log.info("clone repo %s", REPO)
        idk_git.clone(REPO)

    @classmethod
    def tearDownClass(cls):
        system("rm -rf %s" % ROOTDIR)


    def setUp(self):
        """
        Setup the test case
        """
        log.debug("Test good git directory")
        self.idk_git = IDKGit(ROOTDIR)
        self.assertTrue(self.idk_git)
        self.assertTrue(self.idk_git.repo)
        self.assertTrue(self.idk_git.repo.isValid())


    def test_bad_repo(self):
        """
        Test git
        """
        log.debug("Test non-git directory")
        with self.assertRaises(InvalidGitRepo):
            fail_git = IDKGit("/tmp")
            fail_git.branches()

    def test_branch(self):
        branches = self.idk_git.branches()
        log.debug( "Branches found: %s", branches)

        # Add a branch
        branch_name = 'test_idk_branch'
        self.idk_git.create_branch(branch_name)
        branches = self.idk_git.branches()
        log.debug( "Branches found: %s", branches)
        self.assertTrue(branch_name in branches)

        # add the same branch again
        with self.assertRaises(GitCommandException):
            self.idk_git.create_branch(branch_name)

        # switch to the new branch
        self.idk_git.switch_branch(branch_name)
        self.assertEqual(self.idk_git.get_current_branch(), branch_name)

        # switch to the master
        self.idk_git.switch_branch('master')
        self.assertEqual(self.idk_git.get_current_branch(), 'master')

        # switch to an unknown branch
        with self.assertRaises(GitCommandException):
            self.idk_git.switch_branch('fffsssaaa')






    
