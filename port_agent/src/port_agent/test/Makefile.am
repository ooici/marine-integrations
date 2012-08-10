AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings
DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/port_agent/libport_agent.a \
          $(GTEST_MAIN)

####
#    Test Definitions
####
noinst_PROGRAMS = logger_test

logger_test_SOURCES = logger_test.cxx 
logger_test_LDADD = $(DEPLIBS) -lgtest

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
