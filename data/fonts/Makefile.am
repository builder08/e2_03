#
# WARNING: If you modify the files installed here, change the version
# number of the enigma2-fonts package in enigma2.bb.
#
installdir = $(datadir)/fonts

dist_install_DATA = \
	ae_AlMateen.ttf \
	andale.ttf \
	lcd.ttf \
	md_khmurabi_10.ttf \
	time.ttf \
	DejaVuSans.ttf \
	nmsbd.ttf \
	LiberationSans-Bold.ttf \
	LiberationSans-BoldItalic.ttf \
	LiberationSans-Italic.ttf \
	LiberationSans-Regular.ttf \
	wqy-microhei.ttc \
	AbyssinicaSIL-Regular.ttf \
	Roboto-Black.ttf \
	Roboto-BlackItalic.ttf \
	Roboto-Bold.ttf \
	Roboto-BoldItalic.ttf

install-data-hook:
	cd $(DESTDIR)$(datadir)/fonts && \
	$(LN_S) wqy-microhei.ttc fallback.font
