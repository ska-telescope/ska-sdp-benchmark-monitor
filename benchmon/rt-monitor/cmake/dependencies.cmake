set(FETCHCONTENT_BASE_DIR "${CMAKE_BINARY_DIR}/_deps")

include(FetchContent)
include(find_external)

find_package(OpenSSL REQUIRED)
find_package(ICU COMPONENTS uc data i18n io)


# Try to find system Boost first
find_package(Boost)
if(Boost_FOUND)
  message(STATUS "Found system Boost: ${Boost_INCLUDE_DIRS}")
  if(NOT TARGET Boost::boost)
    add_library(Boost::boost INTERFACE IMPORTED)
    set_target_properties(Boost::boost PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${Boost_INCLUDE_DIRS}")
  endif()
else()
  message(STATUS "System Boost not found, downloading...")
  FetchContent_Declare(
    Boost
    GIT_REPOSITORY "https://github.com/boostorg/boost.git"
    GIT_TAG "boost-1.85.0"
    GIT_PROGRESS ON
    GIT_SHALLOW ON
    OVERRIDE_FIND_PACKAGE TRUE EXCLUDE_FROM_ALL)
  FetchContent_MakeAvailable(Boost)
  
  if(NOT TARGET Boost::boost)
    add_library(Boost::boost INTERFACE IMPORTED)
    set_target_properties(Boost::boost PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${boost_SOURCE_DIR}")
  endif()
endif()



# Try to find system cpr first
find_package(cpr QUIET)
if(cpr_FOUND AND TARGET cpr::cpr)
  message(STATUS "Found system cpr")
else()
  message(STATUS "System cpr not found, downloading...")
  
  # Declare curl explicitly to use git instead of URL download which is timing out
  FetchContent_Declare(
    curl
    GIT_REPOSITORY https://github.com/curl/curl.git
    GIT_TAG curl-8_13_0
  )

  FetchContent_Declare(
    cpr
    GIT_REPOSITORY https://github.com/libcpr/cpr.git
    GIT_TAG da40186618909b1a7363d4e4495aa899c6e0eb75
    SOURCE_DIR ${CMAKE_BINARY_DIR}/_deps/cpr-src
  )
  FetchContent_MakeAvailable(cpr)
endif()

# Try to find system spdlog first
find_package(spdlog QUIET)
if(spdlog_FOUND)
  message(STATUS "Found system spdlog")
else()
  message(STATUS "System spdlog not found, downloading...")
  FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG 486b55554f11c9cccc913e11a87085b2a91f706f)
  FetchContent_MakeAvailable(spdlog)
endif()

FetchContent_Declare(
  scn
  GIT_REPOSITORY https://github.com/eliaskosunen/scnlib.git
  GIT_TAG e937be1a52588621b406d58ce8614f96bb5de747)

# Try to find system scn first
find_package(scn QUIET)
if(scn_FOUND)
  message(STATUS "Found system scn")
else()
  message(STATUS "System scn not found, downloading...")
  FetchContent_MakeAvailable(scn)
endif()

find_external(
  influxdb-cxx
  GIT_REPOSITORY
  https://github.com/offa/influxdb-cxx.git
  GIT_TAG
  7582c5071b36ce1daf46a33869c3962616c82325
  DEPENDENCIES
  Boost
  cpr)
