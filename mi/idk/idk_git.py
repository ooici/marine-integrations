"""
@file mi/idk/idk_git.py
@author Bill French
@brief Object to manage git requests

The intent is to not use any pyon code so this script can be run
independantly.
"""

from os.path import dirname
from os import environ
from git import LocalRepository
from git.exceptions import GitCommandFailedException

from mi.core.log import log
from mi.idk.config import Config

from mi.idk.exceptions import InvalidGitRepo
from mi.idk.exceptions import GitCommandException

###
#   IDK Git Tools
###
class IDKGit():
    def __init__(self, rootdir = None):
        if not rootdir:
            self.rootdir = Config().get("working_repo")
        else:
            self.rootdir = rootdir

        # gitpy hardcodes the git command without a path, so it's using PATH to find it.  We need to set the path for
        # git.
        dir = dirname(Config().get('git'))
        environ['PATH'] = "%s:%s" % (dir, environ['PATH'])
        repo = LocalRepository(self.rootdir)

        self.repo = repo


    def _checkRepo(self):
        if not self.repo or not self.repo.isValid():
            log.error("Not a valid Git repo: %s", self.rootdir)
            raise InvalidGitRepo(self.rootdir)


    def clone(self, url):
        self.repo.clone(url)
        self._checkRepo()


    def create_branch(self, branch_name):
        try:
            branch = self.repo.createBranch(branch_name)
            log.info("create git branch %s" % branch_name)
        except GitCommandFailedException, e:
            log.error("failed to create branch %s: %s" % (branch_name, e))
            raise GitCommandException("failed to create branch")

    def _get_branches(self):
        self._checkRepo()
        return self.repo.getBranches()

    def branches(self):
        self._checkRepo()
        retlist = []
        for branch in self._get_branches():
            retlist.append(branch.name)

        return sorted(retlist)

    def switch_branch(self, branch_name):
        self._checkRepo()
        if not self.repo.isWorkingDirectoryClean():
            raise GitCommandException("switch branch failed: working dir not clean")

        log.info("Checkout branch %s" % branch_name)
        try:
            self.repo.checkout(branch_name)
        except GitCommandFailedException, e:
            log.error("failed to switch branch %s: %s" % (branch_name, e))
            raise GitCommandException("failed to switch branch")

    def get_current_branch(self):
        self._checkRepo()
        branch = self.repo.getCurrentBranch()
        return branch.name


