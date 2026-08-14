FROM jacobalberty/cups

ENV CUPS_USER=root
ENV PYTHONPATH=/opt/brother-tools
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      cups-client \
      img2pdf \
      imagemagick \
      iputils-ping \
      libusb-0.1-4 \
      python3 \
      python3-yaml \
      sane-utils \
      wget \
      zip \
  && rm -rf /var/lib/apt/lists/*

# Brother reuses a download id across releases, so the checksum is the only
# thing pinning what actually lands in the image.
COPY packages.sha256 /tmp/packages.sha256
RUN cd /tmp \
  && wget -q \
      https://download.brother.com/welcome/dlf101792/mfcl2700dwcupswrapper-3.2.0-1.i386.deb \
      https://download.brother.com/welcome/dlf101791/mfcl2700dwlpr-3.2.0-1.i386.deb \
      https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb \
      https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.5-0.amd64.deb \
      https://download.brother.com/welcome/dlf006654/brother-udev-rule-type1-1.0.2-0.all.deb \
  && sha256sum -c packages.sha256 \
  && dpkg -i --force-all ./*.deb \
  && rm -f ./*.deb packages.sha256

COPY brother/ /opt/brother-tools/brother/
COPY etc/brother/scan.yaml /etc/brother/scan.yaml
COPY bin/brother-scan /usr/bin/brother-scan
COPY docker-entrypoint.sh /usr/bin/docker-entrypoint-brother.sh
COPY cupds.conf /etc/cups/cupsd.conf

RUN chmod +x /usr/bin/brother-scan /usr/bin/docker-entrypoint-brother.sh \
  && python3 -m compileall -q /opt/brother-tools/brother

VOLUME /scans
ENV SAVETO=/scans

EXPOSE 54925/udp
EXPOSE 54925
EXPOSE 54921
EXPOSE 631

ENTRYPOINT ["/usr/bin/docker-entrypoint-brother.sh"]
CMD ["python3", "-m", "brother.supervisor"]
