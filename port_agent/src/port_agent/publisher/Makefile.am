if HAVE_GMOCK
  SUBDIRS = test
endif

DEPLIBS = $(top_builddir)/src/common/libcommon.a \
          $(top_builddir)/src/port_agent/packet/libport_agent_packet.a 

noinst_LIBRARIES= libport_agent_publisher.a

libport_agent_publisher_a_SOURCES = publisher.cxx publisher.h \
                                    publisher_list.cxx publisher_list.h \
                                    file_publisher.cxx file_publisher.h \
                                    file_pointer_publisher.cxx file_pointer_publisher.h \
                                    instrument_publisher.cxx instrument_publisher.h \
                                    instrument_command_publisher.cxx instrument_command_publisher.h \
                                    instrument_data_publisher.cxx instrument_data_publisher.h \
                                    driver_publisher.cxx driver_publisher.h \
                                    driver_command_publisher.cxx driver_command_publisher.h \
                                    driver_data_publisher.cxx driver_data_publisher.h \
                                    tcp_publisher.cxx tcp_publisher.h \
                                    udp_publisher.cxx udp_publisher.h \
                                    log_publisher.cxx log_publisher.h

libport_agent_publisher_a_CXXFLAGS = -I$(top_builddir)/src
libport_agent_publisher_a_LIBADD = $(DEPLIBS)

include $(top_builddir)/src/Makefile.am.inc
