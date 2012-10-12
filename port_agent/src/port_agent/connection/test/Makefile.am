AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings 
DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/network/libnetwork_comm.a \
          $(top_builddir)/src/port_agent/connection/libport_agent_connection.a \
          $(GTEST_MAIN)

####
#    Test Definitions
####
noinst_PROGRAMS = observatory_connection_test


observatory_connection_test_SOURCES = observatory_connection_test.cxx \
                                      instrument_tcp_connection_test.cxx 

observatory_connection_test_LDADD = $(DEPLIBS) -lgtest

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
