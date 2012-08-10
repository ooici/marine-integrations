AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings
DEPLIBS = $(top_builddir)/src/common/libcommon.a $(GMOCK_MAIN) -lgmock -lgtest

####
#    Test Definitions
####
noinst_PROGRAMS = logger_test \
	              log_file_test \
	              util_test \
                  common_test \
	              logger_test \
	              timestamp_test \
	              spawn_process_test 

log_file_test_SOURCES = log_file_test.cxx 
log_file_test_LDADD = $(DEPLIBS)

common_test_SOURCES = common_test.cxx 
common_test_LDADD = $(DEPLIBS)

spawn_process_test_SOURCES = spawn_process_test.cxx 
spawn_process_test_LDADD = $(DEPLIBS)

logger_test_SOURCES = logger_test.cxx 
logger_test_LDADD = $(DEPLIBS)

util_test_SOURCES = util_test.cxx 
util_test_LDADD = $(DEPLIBS)

timestamp_test_SOURCES = timestamp_test.cxx 
timestamp_test_LDADD = $(DEPLIBS)

TESTS = $(noinst_PROGRAMS)

####
#    Targets for dependancy libraries
####
$(top_builddir)/src/common/libcommon.a:
	cd $(top_builddir)/src/common && $(MAKE) $(MFLAGS) libcommon.a
