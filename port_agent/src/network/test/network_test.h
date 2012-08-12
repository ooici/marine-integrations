#ifndef __NETWORK_TEST_H_
#define __NETWORK_TEST_H_

#include "common/spawn_process.h"
#include "gtest/gtest.h"

#include <spawn.h>
#include <signal.h>

#include <string>

using namespace std;

#define TOOLSDIR "/Users/wfrench/Workspace/code/marine-integrations/port_agent/tools"

class NetworkTest : public testing::Test {
public:
	virtual ~NetworkTest() {}
};


uint16_t startTCPEchoServer(uint16_t port) {
	stringstream cmd;
	uint16_t pid = 0;
	cmd << TOOLSDIR << "/tcp_server_echo.py";

	SpawnProcess process(cmd.str(), 1, "noquit");

	LOG(INFO) << "Start TCP Echo Server: " << process.cmd_as_string();

	bool result = process.run();
    return process.pid();
}

void stopProcess(uint16_t pid) {
    kill(pid, SIGTERM);
}

#endif // __NETWORK_TEST_H_
