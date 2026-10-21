# Native Windows ISO helper; project work: djultra64.
cmake_minimum_required(VERSION 3.25)
project(fnr3_iso_extractor LANGUAGES C)
if(NOT WIN32 OR NOT MINGW)
    message(FATAL_ERROR "The Windows extractor requires a native MinGW-w64 C compiler")
endif()
if(NOT EXISTS "${FNR3_EXTRACT_XISO_SOURCE}/extract-xiso.c")
    message(FATAL_ERROR "Pinned extract-xiso source is unavailable")
endif()
add_executable(extract-xiso "${FNR3_EXTRACT_XISO_SOURCE}/extract-xiso.c")
# Upstream's Win32 getopt compatibility source uses this conventional macro.
target_compile_definitions(extract-xiso PRIVATE WIN32)
# The helper is launched from support/ and must need only Windows system DLLs.
target_link_options(extract-xiso PRIVATE -static)
