AM_CXXFLAGS = -I$(top_builddir)/src -I.. -Wno-write-strings -DTOOLSDIR=\"$(top_builddir)/tools\"
DEPLIBS = $(top_builddir)/src/network/libnetwork_comm.a \
          $(top_builddir)/src/common/libcommon.a $(GMOCK_MAIN) -lgmock -lgtest

####
#    Test Definitions
####
noinst_PROGRAMS = tcp_comm_socket_test \
                  udp_comm_socket_test \
                  tcp_comm_listen_test

tcp_comm_socket_test_SOURCES = tcp_comm_socket_test.cxx 
tcp_comm_socket_test_LDADD = $(DEPLIBS)

udp_comm_socket_test_SOURCES = udp_comm_socket_test.cxx 
udp_comm_socket_test_LDADD = $(DEPLIBS)

tcp_comm_listen_test_SOURCES = tcp_comm_listen_test.cxx 
tcp_comm_listen_test_LDADD = $(DEPLIBS)

TESTS = $(noinst_PROGRAMS)

include $(top_builddir)/src/Makefile.am.inc
