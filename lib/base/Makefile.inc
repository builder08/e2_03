noinst_LIBRARIES += base/libenigma_base.a

base_libenigma_base_a_SOURCES = \
	base/buffer.cpp \
	base/cachedtssource.cpp \
	base/cfile.cpp \
	base/connection.cpp \
	base/console.cpp \
	base/e2avahi.cpp \
	base/ebase.cpp \
	base/eenv.cpp \
	base/eerror.cpp \
	base/elock.cpp \
	base/encoding.cpp \
	base/estring.cpp \
	base/freesatv2.cpp \
	base/huffman.cpp \
	base/init.cpp \
	base/internetcheck.cpp \
	base/ioprio.cpp \
	base/message.cpp \
	base/modelinformation.cpp \
	base/nconfig.cpp \
	base/rawfile.cpp \
	base/smartptr.cpp \
	base/thread.cpp \
	base/httpsstream.cpp \
	base/httpstream.cpp \
	base/wrappers.cpp \
	base/esimpleconfig.cpp \
	base/esettings.cpp

EXTRA_DIST += \
	base/eenv.cpp.in

baseincludedir = $(pkgincludedir)/lib/base
baseinclude_HEADERS = \
	base/buffer.h \
	base/cachedtssource.h \
	base/cfile.h \
	base/console.h \
	base/e2avahi.h \
	base/ebase.h \
	base/eenv.h \
	base/eerror.h \
	base/elock.h \
	base/encoding.h \
	base/eptrlist.h \
	base/estring.h \
	base/freesatv2.h \
	base/huffman.h \
	base/i18n.h \
	base/itssource.h \
	base/init.h \
	base/init_num.h \
	base/internetcheck.h \
	base/ioprio.h \
	base/message.h \
	base/modelinformation.h \
	base/nconfig.h \
	base/object.h \
	base/rawfile.h \
	base/ringbuffer.h \
	base/smartptr.h \
	base/thread.h \
	base/httpsstream.h \
	base/httpstream.h \
	base/wrappers.h \
	base/esimpleconfig.h \
	base/profile.h \
	base/esettings.h
