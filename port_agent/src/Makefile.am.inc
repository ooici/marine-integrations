$(top_builddir)/src/common/libcommon.a:
	cd $(top_builddir)/src/common && $(MAKE) $(MFLAGS) libcommon.a

$(top_builddir)/src/network/libnetwork_comm.a:
	cd $(top_builddir)/src/network && $(MAKE) $(MFLAGS) libnetwork_comm.a

$(top_builddir)/src/port_agent/config/libport_agent_config.a:
	cd $(top_builddir)/src/port_agent/config && $(MAKE) $(MFLAGS) libport_agent_config.a

$(top_builddir)/src/port_agent/connection/libport_agent_connection.a:
	cd $(top_builddir)/src/port_agent/connection && $(MAKE) $(MFLAGS) libport_agent_connection.a

$(top_builddir)/src/port_agent/libport_agent.a:
	cd $(top_builddir)/src/port_agent && $(MAKE) $(MFLAGS) libport_agent.a

$(top_builddir)/src/port_agent/packet/libport_agent_packet.a:
	cd $(top_builddir)/src/port_agent/packet && $(MAKE) $(MFLAGS) libport_agent_packet.a

$(top_builddir)/src/port_agent/publisher/libport_agent_publisher.a:
	cd $(top_builddir)/src/port_agent/publisher && $(MAKE) $(MFLAGS) libport_agent_publisher.a

