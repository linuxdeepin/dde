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
Requires:   lightdm-gtk-greeter
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
Requires:   deepin-pw-check
Requires:   dtkcore
Requires:   dtkgui
Requires:   dtkwidget
Requires:   dde-qt5integration
Requires:   startdde
Requires:   uos-license-content
Requires:   dde-qt5xcb-plugin
Requires:   dde-api
##  其他
Requires:   deepin-desktop-server
Requires:   deepin-icon-theme
Requires:   deepin-gtk-theme
Requires:   deepin-sound-theme
Requires:   deepin-font-manager
##  欢迎  
Requires:   dde-introduction
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
Requires:   dde-printer 
Requires:   deepin-ab-recovery
Requires:   deepin-calculator
Requires:   deepin-compressor
Requires:   deepin-devicemanager
Requires:   deepin-draw
Requires:   deepin-editor
Requires:   deepin-image-viewer
Requires:   deepin-log-viewer
Requires:   deepin-manual
Requires:   deepin-reader
Requires:   deepin-screen-recorder
Requires:   deepin-screensaver
Requires:   org.deepin.downloader
Requires:   deepin-diskmanager
Requires:   deepin-terminal
Requires:   deepin-picker
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
Requires:   uos-license-mini
## 需求
# support exfat
Requires:   exfat-utils
Requires:   fuse-exfat
##  bugfix
##  fix messages error
Requires:   gnome-keyring
##  fix translation error
Requires:   qt5-qttranslations

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

