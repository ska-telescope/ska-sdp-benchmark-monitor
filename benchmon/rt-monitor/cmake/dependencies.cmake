set(FETCHCONTENT_BASE_DIR "${CMAKE_BINARY_DIR}/_deps")

include(FetchContent)
include(find_external)

FetchContent_Declare(
  openssl
  GIT_REPOSITORY https://github.com/openssl/openssl.git
  GIT_TAG 7b371d80d959ec9ab4139d09d78e83c090de9779
  FIND_PACKAGE_ARGS NAMES openssl)

FetchContent_MakeAvailable(openssl)
find_package(OpenSSL REQUIRED)

FetchContent_Declare(
  Boost
  GIT_REPOSITORY "https://github.com/boostorg/boost.git"
  GIT_TAG "boost-1.85.0"
  GIT_PROGRESS ON
  GIT_SHALLOW ON
  OVERRIDE_FIND_PACKAGE TRUE EXCLUDE_FROM_ALL)

add_library(Boost::boost INTERFACE IMPORTED)

set_target_properties(Boost::boost PROPERTIES INTERFACE_INCLUDE_DIRECTORIES
                                              "${boost_SOURCE_DIR}")

FetchContent_Declare(
  cpr
  GIT_REPOSITORY https://github.com/libcpr/cpr.git
  GIT_TAG da40186618909b1a7363d4e4495aa899c6e0eb75
  FIND_PACKAGE_ARGS NAMES cpr)

FetchContent_Declare(
  spdlog
  GIT_REPOSITORY https://github.com/gabime/spdlog.git
  GIT_TAG 486b55554f11c9cccc913e11a87085b2a91f706f
  FIND_PACKAGE_ARGS NAMES spdlog)

FetchContent_MakeAvailable(Boost cpr spdlog)

FetchContent_Declare(
  scn
  GIT_REPOSITORY https://github.com/eliaskosunen/scnlib.git
  GIT_TAG e937be1a52588621b406d58ce8614f96bb5de747
  FIND_PACKAGE_ARGS NAMES scn)

FetchContent_MakeAvailable(scn)

find_external(
  influxdb-cxx
  GIT_REPOSITORY
  https://github.com/offa/influxdb-cxx.git
  GIT_TAG
  7582c5071b36ce1daf46a33869c3962616c82325
  DEPENDENCIES
  Boost
  cpr)
