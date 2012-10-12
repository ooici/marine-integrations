if HAVE_GMOCK
  SUBDIRS = test
endif

noinst_LIBRARIES= libnetwork_comm.a

libnetwork_comm_a_SOURCES = comm_base.cxx comm_base.h \
                            comm_listener.cxx comm_listener.h \
                            tcp_comm_listener.cxx tcp_comm_listener.h \
                            comm_socket.cxx comm_socket.h \
                            tcp_comm_socket.cxx tcp_comm_socket.h \
                            udp_comm_socket.cxx udp_comm_socket.h \
                            serial_comm_socket.cxx serial_comm_socket.h 

libnetwork_comm_a_CXXFLAGS = -I$(top_builddir)/src
libnetwork_comm_a_LIBADD = $(top_builddir)/src/common/libcommon.a

include $(top_builddir)/src/Makefile.am.inc
