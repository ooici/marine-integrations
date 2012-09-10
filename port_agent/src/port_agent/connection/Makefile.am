if HAVE_GMOCK
  SUBDIRS = test
endif

noinst_LIBRARIES= libport_agent_connection.a

libport_agent_connection_a_SOURCES = connection.cxx connection.h \
                                     instrument_tcp_connection.cxx instrument_tcp_connection.h \
                                     observatory_connection.cxx observatory_connection.h

libport_agent_connection_a_CXXFLAGS = -I$(top_builddir)/src
libport_agent_connection_a_LIBADD = $(top_builddir)/src/common/libcommon.a \
                                    $(top_builddir)/src/network/libnetwork_comm.a 

include $(top_builddir)/src/Makefile.am.inc
