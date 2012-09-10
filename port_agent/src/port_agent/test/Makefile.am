AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings -DTOOLSDIR=\"$(top_builddir)/tools\"
DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/port_agent/libport_agent.a \
          $(top_builddir)/src/port_agent/config/libport_agent_config.a \
          $(top_builddir)/src/port_agent/packet/libport_agent_packet.a \
          $(top_builddir)/src/port_agent/connection/libport_agent_connection.a \
          $(top_builddir)/src/network/libnetwork_comm.a \
          $(GTEST_MAIN)

####
#    Test Definitions
####
noinst_PROGRAMS = port_agent_test

port_agent_test_SOURCES = port_agent_test.cxx 
port_agent_test_LDADD = $(DEPLIBS) -lgtest

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
