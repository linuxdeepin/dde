Name:      dde
Version:   2021.4.15
Release:   %{specrelease}
Summary:   Deepin New Desktop Environment - Next
License:   GPLv3
URL:       https://github.com/linuxdeepin/dde

Source0:   %{url}/archive/%{version}/%{name}-%{version}.tar.gz

Requires:  lightdm
Requires:  lightdm-gtk-greeter
Requires:  mesa-dri-drivers
Requires:  xorg-x11-server-Xorg
Requires:  gnome-keyring
Requires:  librsvg2-tools
## translation
Requires:  qt5-qttranslations
## input method
Requires:  fcitx fcitx-qt5 fcitx-pinyin fcitx-sunpinyin fcitx-configtool fcitx-table-chinese
## DDE
Requires:  dde-api
Requires:  dde-kwin
Requires:  dde-dock
Requires:  dde-daemon
Requires:  dde-desktop
Requires:  dde-launcher
Requires:  startdde
Requires:  dde-polkit-agent
Requires:  dde-file-manager
Requires:  dde-account-faces
Requires:  dde-control-center
Requires:  dde-session-shell
Requires:  dde-session-ui
Requires:  dde-qt-dbus-factory
Requires:  dde-disk-mount-plugin
Requires:  dde-dock-onboard-plugin
Requires:  dde-qt5integration
Requires:  dde-qt5dxcb-plugin
Requires:  dde-network-utils
Requires:  dde-introduction
Requires:  dde-clipboard
Requires:  deepin-default-settings
Requires:  deepin-qml-widgets
Requires:  deepin-menu
Requires:  deepin-desktop-base
Requires:  deepin-icon-theme
Requires:  deepin-desktop-schemas
Requires:  deepin-system-monitor
Requires:  deepin-wallpapers
Requires:  deepin-gtk-theme
Requires:  deepin-authenticate
Requires:  deepin-keyring
# nofreee
Requires:  uos-license-content
## application
Recommends:  dde-device-formatter
Recommends:  deepin-calculator
Recommends:  deepin-screen-recorder
Recommends:  deepin-screensaver
Recommends:  deepin-draw
Recommends:  dde-printer
Recommends:  dde-calendar
Recommends:  deepin-editor
Recommends:  deepin-image-viewer
Recommends:  deepin-shortcut-viewer
Recommends:  deepin-sound-theme
Recommends:  deepin-terminal
Recommends:  blur-effect
Recommends:  deepin-ab-recovery
Recommends:  deepin-compressor
Recommends:  deepin-devicemanager
Recommends:  deepin-elf-verify
Recommends:  deepin-font-manager
Recommends:  deepin-graphics-driver-manager
Recommends:  deepin-log-viewer
Recommends:  deepin-reader
Recommends:  libpam-deepin-security
Recommends:  deepin-manual

# support exfat
Recommends: exfat-utils fuse-exfat

## bugfix50260
Obsoletes:  deepin-picker <= 5.0.10

%description
Deepin New Desktop Environment.

%prep
%setup -q -n %{name}-%{version}

%build
echo "build"

%install
mkdir -p %{buildroot}/etc/{rsyslog.d,logrotate.d}

install -Dm644 rpm/dde.conf %{buildroot}/etc/rsyslog.d/dde.conf
install -Dm644 rpm/dde %{buildroot}/etc/logrotate.d/dde

%files
%{_sysconfdir}/rsyslog.d/dde.conf
%{_sysconfdir}/logrotate.d/dde

%changelog
* Tue Apr 15 2021 uoser <uoser@uniontech.com> - 2021.4.15-1
- update to 2021.4.15-1



