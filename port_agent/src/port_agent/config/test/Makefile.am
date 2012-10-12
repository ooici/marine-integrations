AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings
DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/port_agent/config/libport_agent_config.a \
          $(GTEST_MAIN)

####
#    Test Definitions
####
noinst_PROGRAMS = config_test

config_test_SOURCES = config_test.cxx 
config_test_LDADD = $(DEPLIBS) -lgtest

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
