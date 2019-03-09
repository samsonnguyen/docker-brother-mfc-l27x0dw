FROM jacobalberty/cups
ENV CUPS_USER=root
RUN apt-get update && apt-get install -y wget \
  sane-utils \
  imagemagick \
  cups-client \
  zip \
  iputils-ping
RUN wget https://download.brother.com/welcome/dlf103526/mfcl2710dwpdrv-4.0.0-1.i386.deb
RUN dpkg -i --force-all mfcl2710dwpdrv-4.0.0-1.i386.deb
RUN wget https://download.brother.com/welcome/dlf006645/brscan4-0.4.7-1.amd64.deb
RUN dpkg -i --force-all brscan4-0.4.7-1.amd64.deb
RUN wget https://download.brother.com/welcome/dlf006652/brscan-skey-0.2.4-1.amd64.deb
RUN dpkg -i --force-all brscan-skey-0.2.4-1.amd64.deb 
EXPOSE 54925/udp
COPY docker-entrypoint.sh /usr/bin/docker-entrypoint-brother.sh
RUN chmod +x /usr/bin/docker-entrypoint-brother.sh
ENTRYPOINT ["/usr/bin/docker-entrypoint-brother.sh"]
CMD ["brscan-skey","-f"]