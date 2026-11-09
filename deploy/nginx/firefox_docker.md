# docker-compose文件内容


```
services:
  firefox:
    build: .
    image: yianso/firefox-fcitx:local
    network_mode: host
    environment:
      - TZ=Asia/Shanghai
      - DISPLAY_WIDTH=1920
      - DISPLAY_HEIGHT=1080
      - KEEP_APP_RUNNING=1
      - ENABLE_CJK_FONT=0
      - VNC_PASSWORD=${VNC_PASSWORD}
      - PACKAGES_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/alpine
      - WEB_LISTENING_PORT=${FIREFOX_VNC_PORT}
      - VNC_LISTENING_PORT=-1
      - FF_OPEN_URL=https://yuanbao.tencent.com/
      - LANG=zh_CN.UTF-8
      - GTK_IM_MODULE=fcitx
      - QT_IM_MODULE=fcitx
      - XMODIFIERS=@im=fcitx
      - WEB_HOST_CLIPBOARD_SYNC=1
    volumes:
      - ${APP_PATH}/data/config:/config:rw
    shm_size: 2g
    restart: always
    labels:
      createdBy: "bt_apps"
```

# .env

```
FIREFOX_VNC_PORT=5800
#FIREFOX_VNC_SERVER_PORT#FIREFOX_VNC_SERVER_PORT=5900
VNC_PASSWORD=qwer@123
INSTALL_FONT=0
HOST_IP=0.0.0.0
CPUS=0
MEMORY_LIMIT=0MB
APP_PATH=/www/dk_project/dk_app/firefox/firefox_docker
```
