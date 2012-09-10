AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings 
DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/network/libnetwork_comm.a \
          $(top_builddir)/src/port_agent/packet/libport_agent_packet.a \
          $(top_builddir)/src/port_agent/publisher/libport_agent_publisher.a \
          $(GTEST_MAIN)

####
#    Test Definitions
####
noinst_PROGRAMS = log_publisher_test \
                  tcp_publisher_test \
                  udp_publisher_test \
                  driver_command_publisher_test \
                  driver_data_publisher_test \
                  instrument_command_publisher_test \
                  instrument_data_publisher_test \
                  publisher_list_test


log_publisher_test_SOURCES = publisher_test.h log_publisher_test.cxx 
log_publisher_test_LDADD = $(DEPLIBS) -lgtest

tcp_publisher_test_SOURCES = publisher_test.h tcp_publisher_test.cxx 
tcp_publisher_test_LDADD = $(DEPLIBS) -lgtest

udp_publisher_test_SOURCES = publisher_test.h udp_publisher_test.cxx 
udp_publisher_test_LDADD = $(DEPLIBS) -lgtest

driver_command_publisher_test_SOURCES = publisher_test.h driver_command_publisher_test.cxx 
driver_command_publisher_test_LDADD = $(DEPLIBS) -lgtest

driver_data_publisher_test_SOURCES = publisher_test.h driver_data_publisher_test.cxx 
driver_data_publisher_test_LDADD = $(DEPLIBS) -lgtest

instrument_command_publisher_test_SOURCES = publisher_test.h instrument_command_publisher_test.cxx 
instrument_command_publisher_test_LDADD = $(DEPLIBS) -lgtest

instrument_data_publisher_test_SOURCES = publisher_test.h instrument_data_publisher_test.cxx 
instrument_data_publisher_test_LDADD = $(DEPLIBS) -lgtest

publisher_list_test_SOURCES = publisher_test.h publisher_list_test.cxx 
publisher_list_test_LDADD = $(DEPLIBS) -lgtest

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
