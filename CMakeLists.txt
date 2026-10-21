# fnr3 - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(fnr3 VERSION 0.7.0 DESCRIPTION "Fight Night Round 3 Recomp" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(FNR3_SOURCES
    src/main.cpp
    src/port_graphics.cpp
    src/port_frontend.cpp
    src/port_menu.cpp
    src/port_input.cpp
    src/port_frame_times.cpp
)
# Original guest clock only. Archived 60Hz/interpolation renderer experiments
# remain outside the production target.

if(WIN32)
    add_executable(fnr3 WIN32 ${FNR3_SOURCES})
else()
    add_executable(fnr3 ${FNR3_SOURCES})
endif()

rexglue_setup_target(fnr3 GPU_PLUGINS xenos)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(fnr3 PRIVATE "-Wl,--export-dynamic-symbol=Fnr3GetInputGlyphBridge")
endif()

# The 0.10.0 installed SDK stages runtime libraries on Windows/macOS only.
# Linux uses $ORIGIN, so place its imported shared libraries beside the host.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    foreach(runtime_target rex::runtime rex::TracyClient)
      if(TARGET ${runtime_target})
        add_custom_command(TARGET fnr3 POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:${runtime_target}>
                $<TARGET_FILE_DIR:fnr3>
            VERBATIM
        )
      endif()
    endforeach()
endif()

# An explicit override keeps local SDK fixes from being overwritten on relink.
set(FNR3_GPU_PLUGIN_FILE "" CACHE FILEPATH "Patched GPU plugin to stage beside fnr3")
if(FNR3_GPU_PLUGIN_FILE)
    if(NOT EXISTS "${FNR3_GPU_PLUGIN_FILE}")
        message(FATAL_ERROR "Patched GPU plugin does not exist: ${FNR3_GPU_PLUGIN_FILE}")
    endif()
    set(fnr3_staged_gpu "${FNR3_GPU_PLUGIN_FILE}")
else()
    set(fnr3_staged_gpu "$<TARGET_FILE:rex::gpu-xenos>")
endif()
add_custom_target(fnr3_stage_gpu ALL
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${fnr3_staged_gpu}" $<TARGET_FILE_DIR:fnr3>
    DEPENDS fnr3
    VERBATIM
)
