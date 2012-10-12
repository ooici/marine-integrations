AC_INIT( [ooi], [1.0], [wfrench@ucsd.edu] )
AM_INIT_AUTOMAKE([subdir-objects -Wall -Wno-extra-portability -Werror foreign])

# Check for programs 
AC_PROG_CC
AC_PROG_CXX
AC_PROG_RANLIB

# Not sure if we need a config.h right now.  Uncomment this if we end up 
# needing a package configuration file.
# AC_CONFIG_HEADERS([config.h])

# Our configuration files
AC_CONFIG_FILES([
  Makefile
  src/Makefile
  src/network/Makefile
  src/network/test/Makefile
  src/common/Makefile
  src/common/test/Makefile
  src/port_agent/Makefile
  src/port_agent/test/Makefile
  src/port_agent/config/Makefile
  src/port_agent/config/test/Makefile
  src/port_agent/packet/Makefile
  src/port_agent/packet/test/Makefile
  src/port_agent/connection/Makefile
  src/port_agent/connection/test/Makefile
  src/port_agent/publisher/Makefile
  src/port_agent/publisher/test/Makefile
])

# GoogleTest in the testing framework we use.  The google test checks
# were ripped from the configure.ac of GoogleMock
AC_ARG_WITH([gmock],
            [AS_HELP_STRING([--with-gmock],
                            [Specifies how to find the gmock package. If no
                            arguments are given, the default behavior, a
                            system installed gmock will be used if present,
                            and an internal version built otherwise. If a
                            path is provided, the gmock built or installed at
                            that prefix will be used.])],
            [],
            [with_gmock=yes])
AC_ARG_ENABLE([external-gmock],
              [AS_HELP_STRING([--disable-external-gmock],
                              [Disables any detection or use of a system
                              installed or user provided gmock. Any option to
                              '--with-gmock' is ignored. (Default is enabled.)])
              ], [], [enable_external_gmock=yes])
AS_IF([test "x$with_gmock" == "xno"],
      [AC_MSG_ERROR([dnl
Support for GoogleTest was explicitly disabled. Currently GoogleMock has a hard
dependency upon GoogleTest to build, please provide a version, or allow
GoogleMock to use any installed version and fall back upon its internal
version.])])

# Setup various GMOCK variables. TODO(chandlerc@google.com): When these are
# used below, they should be used such that any pre-existing values always
# trump values we set them to, so that they can be used to selectively override
# details of the detection process.
AC_ARG_VAR([GMOCK_CONFIG],
           [The exact path of Google Test's 'gmock-config' script.])
AC_ARG_VAR([GMOCK_CPPFLAGS],
           [C-like preprocessor flags for Google Test.])
AC_ARG_VAR([GMOCK_CXXFLAGS],
           [C++ compile flags for Google Test.])
AC_ARG_VAR([GMOCK_LDFLAGS],
           [Linker path and option flags for Google Test.])
AC_ARG_VAR([GMOCK_LIBS],
           [Library linking flags for Google Test.])
AC_ARG_VAR([GMOCK_VERSION],
           [The version of Google Test available.])
AC_ARG_VAR([GMOCK_LIBDIR],
           [Google library path.])
AC_ARG_VAR([GMOCK_MAIN],
           [Google mock library with the main function.])
HAVE_BUILT_GMOCK="no"

GMOCK_MIN_VERSION="1.5.0"

AS_IF([test "x${enable_external_gmock}" = "xyes"],
      [# Begin filling in variables as we are able.
      AS_IF([test "x${with_gmock}" != "xyes"],
            [AS_IF([test -x "${with_gmock}/scripts/gmock-config"],
                   [GMOCK_CONFIG="${with_gmock}/scripts/gmock-config"],
                   [GMOCK_CONFIG="${with_gmock}/bin/gmock-config"])
            AS_IF([test -x "${GMOCK_CONFIG}"], [],
                  [AC_MSG_ERROR([dnl
Unable to locate either a built or installed Google Test at '${with_gmock}'.])
                  ])])

      AS_IF([test -x "${GMOCK_CONFIG}"], [],
            [AC_PATH_PROG([GMOCK_CONFIG], [gmock-config])])
      AS_IF([test -x "${GMOCK_CONFIG}"],
            [AC_MSG_CHECKING([for Google Test version >= ${GMOCK_MIN_VERSION}])
            AS_IF([${GMOCK_CONFIG} --min-version=${GMOCK_MIN_VERSION}],
                  [AC_MSG_RESULT([yes])
                  HAVE_BUILT_GMOCK="yes"],
                  [AC_MSG_RESULT([no])])])])

AS_IF([test "x${HAVE_BUILT_GMOCK}" = "xyes"],
      [GMOCK_CPPFLAGS=`${GMOCK_CONFIG} --cppflags`
      GMOCK_CXXFLAGS=`${GMOCK_CONFIG} --cxxflags`
      GMOCK_LDFLAGS=`${GMOCK_CONFIG} --ldflags`
      GMOCK_LIBS=`${GMOCK_CONFIG} --libs`
      GMOCK_VERSION=`${GMOCK_CONFIG} --version`
      GMOCK_LIBDIR=`${GMOCK_CONFIG} --libdir`
      GMOCK_MAIN="${GMOCK_LIBDIR}/libgmock_main.a"],
      [AC_CONFIG_SUBDIRS([gmock])
      # GMOCK_CONFIG needs to be executable both in a Makefile environmont and
      # in a shell script environment, so resolve an absolute path for it here.
      GMOCK_CONFIG="`pwd -P`/gmock/scripts/gmock-config"
      GMOCK_CPPFLAGS='-I$(top_srcdir)/gmock/include'
      GMOCK_CXXFLAGS='-g'
      GMOCK_LDFLAGS=''
      GMOCK_LIBS='$(top_builddir)/gmock/lib/libgmock.la'
      GMOCK_VERSION="${GMOCK_MIN_VERSION}"])

AM_CONDITIONAL([HAVE_GMOCK],[test -x ${GMOCK_CONFIG}])
#AS_IF([test -x ${GMOCK_CONFIG}], [AC_DEFINE(HAVE_GMOCK)])



# GoogleTest in the testing framework we use.  The google test checks
# were ripped from the configure.ac of GoogleMock
AC_ARG_WITH([gtest],
            [AS_HELP_STRING([--with-gtest],
                            [Specifies how to find the gtest package. If no
                            arguments are given, the default behavior, a
                            system installed gtest will be used if present,
                            and an internal version built otherwise. If a
                            path is provided, the gtest built or installed at
                            that prefix will be used.])],
            [],
            [with_gtest=yes])
AC_ARG_ENABLE([external-gtest],
              [AS_HELP_STRING([--disable-external-gtest],
                              [Disables any detection or use of a system
                              installed or user provided gtest. Any option to
                              '--with-gtest' is ignored. (Default is enabled.)])
              ], [], [enable_external_gtest=yes])
AS_IF([test "x$with_gtest" == "xno"],
      [AC_MSG_ERROR([dnl
Support for GoogleTest was explicitly disabled. Currently GoogleMock has a hard
dependency upon GoogleTest to build, please provide a version, or allow
GoogleMock to use any installed version and fall back upon its internal
version.])])

# Setup various GTEST variables. TODO(chandlerc@google.com): When these are
# used below, they should be used such that any pre-existing values always
# trump values we set them to, so that they can be used to selectively override
# details of the detection process.
AC_ARG_VAR([GTEST_CONFIG],
           [The exact path of Google Test's 'gtest-config' script.])
AC_ARG_VAR([GTEST_CPPFLAGS],
           [C-like preprocessor flags for Google Test.])
AC_ARG_VAR([GTEST_CXXFLAGS],
           [C++ compile flags for Google Test.])
AC_ARG_VAR([GTEST_LDFLAGS],
           [Linker path and option flags for Google Test.])
AC_ARG_VAR([GTEST_LIBS],
           [Library linking flags for Google Test.])
AC_ARG_VAR([GTEST_VERSION],
           [The version of Google Test available.])
AC_ARG_VAR([GTEST_LIBDIR],
           [Google library path.])
AC_ARG_VAR([GTEST_MAIN],
           [Google mock library with the main function.])
HAVE_BUILT_GTEST="no"

GTEST_MIN_VERSION="1.5.0"

AS_IF([test "x${enable_external_gtest}" = "xyes"],
      [# Begin filling in variables as we are able.
      AS_IF([test "x${with_gtest}" != "xyes"],
            [AS_IF([test -x "${with_gtest}/scripts/gtest-config"],
                   [GTEST_CONFIG="${with_gtest}/scripts/gtest-config"],
                   [GTEST_CONFIG="${with_gtest}/bin/gtest-config"])
            AS_IF([test -x "${GTEST_CONFIG}"], [],
                  [AC_MSG_ERROR([dnl
Unable to locate either a built or installed Google Test at '${with_gtest}'.])
                  ])])

      AS_IF([test -x "${GTEST_CONFIG}"], [],
            [AC_PATH_PROG([GTEST_CONFIG], [gtest-config])])
      AS_IF([test -x "${GTEST_CONFIG}"],
            [AC_MSG_CHECKING([for Google Test version >= ${GTEST_MIN_VERSION}])
            AS_IF([${GTEST_CONFIG} --min-version=${GTEST_MIN_VERSION}],
                  [AC_MSG_RESULT([yes])
                  HAVE_BUILT_GTEST="yes"],
                  [AC_MSG_RESULT([no])])])])

AS_IF([test "x${HAVE_BUILT_GTEST}" = "xyes"],
      [GTEST_CPPFLAGS=`${GTEST_CONFIG} --cppflags`
      GTEST_CXXFLAGS=`${GTEST_CONFIG} --cxxflags`
      GTEST_LDFLAGS=`${GTEST_CONFIG} --ldflags`
      GTEST_LIBS=`${GTEST_CONFIG} --libs`
      GTEST_VERSION=`${GTEST_CONFIG} --version`
      GTEST_LIBDIR=`${GTEST_CONFIG} --libdir`
      GTEST_MAIN="${GTEST_LIBDIR}/libgtest_main.a"],
      [AC_CONFIG_SUBDIRS([gtest])
      # GTEST_CONFIG needs to be executable both in a Makefile environmont and
      # in a shell script environment, so resolve an absolute path for it here.
      GTEST_CONFIG="`pwd -P`/gtest/scripts/gtest-config"
      GTEST_CPPFLAGS='-I$(top_srcdir)/gtest/include'
      GTEST_CXXFLAGS='-g'
      GTEST_LDFLAGS=''
      GTEST_LIBS='$(top_builddir)/gtest/lib/libgtest.la'
      GTEST_VERSION="${GTEST_MIN_VERSION}"])

AM_CONDITIONAL([HAVE_GTEST],[test -x ${GTEST_CONFIG}])
#AS_IF([test -x ${GTEST_CONFIG}], [AC_DEFINE(HAVE_GTEST)])


###
#   Check for socat. If socat is not present all dependant tests will be 
#   skipped.
###
AC_ARG_VAR([SOCAT], [The exact path of the socat executable])
AC_PATH_PROG([SOCAT], [socat],[:])
AM_CONDITIONAL([HAVE_SOCAT],[test "SOCAT" != ":"])
AS_IF([test -x ${SOCAT}], 
  [AC_DEFINE(HAVE_SOCAT)],
  [AC_DEFINE(NO_SOCAT)])
AC_DEFINE_UNQUOTED([SOCAT], "$SOCAT")

# All Done.  Time to write.
AC_OUTPUT
