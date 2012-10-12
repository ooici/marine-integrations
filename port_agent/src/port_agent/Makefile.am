SUBDIRS = packet publisher config connection

if HAVE_GMOCK
  SUBDIRS += test
endif

###
#   Port agent library
###
noinst_LIBRARIES= libport_agent.a

libport_agent_a_SOURCES = port_agent.cxx port_agent.h

libport_agent_a_CXXFLAGS = -I$(top_builddir)/src
libport_agent_a_LIBADD = $(top_builddir)/src/common/libcommon.a \
                         $(top_builddir)/src/port_agent/config/libport_agent_config.a \
                         $(top_builddir)/src/port_agent/connection/libport_agent_connection.a \
                         $(top_builddir)/src/port_agent/packet/libport_agent_packet.a \
                         $(top_builddir)/src/network/libnetwork_comm.a

###
#   Executable
###
bin_PROGRAMS = port_agent
port_agent_SOURCES = port_agent_main.cxx
port_agent_CXXFLAGS = -I$(top_builddir)/src
port_agent_LDADD = libport_agent.a $(libport_agent_a_LIBADD)

include $(top_builddir)/src/Makefile.am.inc

