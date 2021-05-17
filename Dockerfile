FROM jacobalberty/cups
ENV CUPS_USER=root
RUN apt-get update && apt-get install -y wget \
  sane-utils \
  imagemagick \
  cups-client \
  zip \
  iputils-ping \
  libusb-0.1-4 \
  img2pdf \
  ruby \
  ruby-byebug \
  && rm -rf /var/lib/apt/lists/*
RUN wget https://download.brother.com/welcome/dlf103526/mfcl2710dwpdrv-4.0.0-1.i386.deb
RUN dpkg -i --force-all mfcl2710dwpdrv-4.0.0-1.i386.deb
RUN wget https://download.brother.com/welcome/dlf105200/brscan4-0.4.10-1.amd64.deb
RUN dpkg -i --force-all brscan4-0.4.10-1.amd64.deb
RUN wget https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.1-2.amd64.deb
RUN dpkg -i --force-all brscan-skey-0.3.1-2.amd64.deb
RUN wget https://download.brother.com/welcome/dlf006654/brother-udev-rule-type1-1.0.2-0.all.deb
RUN dpkg -i brother-udev-rule-type1-1.0.2-0.all.deb

VOLUME /scans
ENV SAVETO=/scans

EXPOSE 54925/udp
EXPOSE 54925
EXPOSE 54921
EXPOSE 631

COPY docker-entrypoint.sh /usr/bin/docker-entrypoint-brother.sh
COPY cupds.conf /etc/cups/cupsd.conf

COPY scripts/* /opt/brother/scanner/brscan-skey/script/
COPY brscan-skey.config /opt/brother/scanner/brscan-skey/brscan-skey.config

RUN chmod +x /usr/bin/docker-entrypoint-brother.sh
ENTRYPOINT ["/usr/bin/docker-entrypoint-brother.sh"]
CMD ["brscan-skey","-f"] # run in foreground
