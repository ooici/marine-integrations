if HAVE_GMOCK
  SUBDIRS = test
endif

noinst_LIBRARIES= libport_agent_config.a

libport_agent_config_a_SOURCES = port_agent_config.cxx port_agent_config.h 

libport_agent_config_a_CXXFLAGS = -I$(top_builddir)/src
libport_agent_config_a_LIBADD = $(top_builddir)/src/common/libcommon.a

include $(top_builddir)/src/Makefile.am.inc
