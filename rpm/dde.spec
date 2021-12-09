%global debug_package %{nil}

Name:       dde
Version:    2021.04.23
Release:    2
Summary:    Deepin New Desktop Environment - Next
License:    GPLv3
URL:        https://github.com/linuxdeepin/dde

Source0:    %{url}/archive/%{version}/%{name}-%{version}.tar.gz

## 底层组件
Requires:   lightdm
Requires:   mesa-dri-drivers
Requires:   xorg-x11-server-Xorg
Requires:   librsvg2-tools
## DDE
Requires:   dde-control-center
Requires:   dde-daemon
Requires:   dde-dock
Requires:   dde-dock-onboard-plugin
Requires:   dde-launcher
Requires:   dde-network-utils
Requires:   dde-polkit-agent
Requires:   dde-preload
Requires:   dde-qt-dbus-factory
Requires:   dde-server-industry-config
Requires:   dde-session-shell
Requires:   dde-session-ui
Requires:   dde-account-faces
Requires:   deepin-default-settings
Requires:   deepin-desktop-schemas
Requires:   deepin-gettext-tools
Requires:   deepin-menu
Requires:   dtkcore
Requires:   dtkgui
Requires:   dtkwidget
Requires:   dde-qt5integration
Requires:   startdde
Requires:   uos-license-content
Requires:   dde-qt5xcb-plugin
Requires:   dde-api
Requires:   dpa-ext-gnomekeyring
Requires:   dtkcommon
##  其他
Requires:   deepin-desktop-server
Requires:   deepin-icon-theme
Requires:   deepin-gtk-theme
Requires:   deepin-sound-theme
##  文管
Requires:   dde-desktop
Requires:   dde-file-manager
Requires:   dde-disk-mount-plugin
Requires:   deepin-wallpapers
Requires:   deepin-shortcut-viewer

##  窗管
Requires:   dde-kwin
##  应用
Requires:   deepin-system-monitor
Requires:   dde-calendar
Requires:   dde-clipboard
Requires:   dde-device-formatter
Requires:   deepin-ab-recovery
Requires:   deepin-calculator
Requires:   deepin-compressor
Requires:   deepin-devicemanager
Requires:   deepin-editor
Requires:   deepin-log-viewer
Requires:   deepin-manual
Requires:   deepin-reader
Requires:   deepin-screen-recorder
Requires:   deepin-screensaver
Requires:   deepin-terminal
Requires:   org.deepin.browser
Requires:   gparted
Requires:   deepin-boot-maker
##  输入法
Requires:   fcitx
Requires:   fcitx-qt5
Requires:   fcitx-pinyin
Requires:   fcitx-configtool
Requires:   fcitx-table-chinese
Requires:   deepin-fcitxconfigtool-plugin
Requires:   fcitx-sunpinyin
Requires:   fcitx-cloudpinyin
## 激活授权
Requires:   deepin-license-activator
## 需求
# support exfat
Requires:   exfat-utils
Requires:   fuse-exfat
##  bugfix
##  fix messages error
Requires:   gnome-keyring
##  fix translation error
Requires:   qt5-qttranslations
Requires:   deepin-pw-check

##  replace uos-license-mini with deepin-license-activator
Obsoletes:  uos-license-mini

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
* Fri Apr 23 2021 uoser <uoser@uniontech.com> - 2021.04.23-2
- update to 2021.04.23-2

