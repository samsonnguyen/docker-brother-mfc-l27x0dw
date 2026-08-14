FROM jacobalberty/cups

ENV CUPS_USER=root
ENV PYTHONPATH=/opt/brother-tools
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      cups-client \
      curl \
      ghostscript \
      img2pdf \
      imagemagick \
      iputils-ping \
      libusb-0.1-4 \
      lib32stdc++6 \
      perl \
      python3 \
      python3-yaml \
      sane-utils \
      wget \
      zip \
  && rm -rf /var/lib/apt/lists/*

# Brother reuses a download id across releases, so the checksum is the only
# thing pinning what actually lands in the image.
COPY packages.sha256 /tmp/packages.sha256
# linux-brprinter-installer stubs /etc/init.d/{cups,lpd,lprng} with /bin/true
# before installing, so the debs' postinst service-restart calls succeed. This
# model's postinst guards them with `if [ -e ]` and skips either way, but the
# stubs cost nothing and keep a future package version from failing here.
# Only --force-architecture is used: the i386 drivers are genuinely foreign-arch,
# but every other failure must surface rather than be forced past.
RUN cd /tmp \
  && wget -q \
      https://download.brother.com/welcome/dlf101792/mfcl2700dwcupswrapper-3.2.0-1.i386.deb \
      https://download.brother.com/welcome/dlf101791/mfcl2700dwlpr-3.2.0-1.i386.deb \
      https://download.brother.com/welcome/dlf105200/brscan4-0.4.11-1.amd64.deb \
      https://download.brother.com/welcome/dlf006652/brscan-skey-0.3.5-0.amd64.deb \
      https://download.brother.com/welcome/dlf006654/brother-udev-rule-type1-1.0.2-0.all.deb \
  && sha256sum -c packages.sha256 \
  && for svc in cups cupsys lpd lprng; do \
       if [ ! -e "/etc/init.d/$svc" ]; then ln -s /bin/true "/etc/init.d/$svc"; echo "$svc" >> /tmp/stubbed; fi; \
     done \
  && dpkg -i --force-architecture ./*.deb \
  && while read -r svc; do rm -f "/etc/init.d/$svc"; done < /tmp/stubbed \
  && rm -f ./*.deb packages.sha256 /tmp/stubbed \
  && apt-get check \
  && test -x /lib/ld-linux.so.2

COPY brother/ /opt/brother-tools/brother/
COPY etc/brother/scan.yaml /etc/brother/scan.yaml
COPY bin/brother-scan /usr/bin/brother-scan
COPY docker-entrypoint.sh /usr/bin/docker-entrypoint-brother.sh
COPY cupds.conf /etc/cups/cupsd.conf

RUN chmod +x /usr/bin/brother-scan /usr/bin/docker-entrypoint-brother.sh \
  && python3 -m compileall -q /opt/brother-tools/brother

# The print path ends in i386 binaries that exit 0 and emit nothing when the
# 32-bit runtime is missing, so CUPS reports success on an empty job. Push a
# real job through the filter at build time and fail if it produces no output.
RUN printf '%%!PS\n/Helvetica findfont 24 scalefont setfont 72 700 moveto (build check) show showpage\n' > /tmp/check.ps \
  && /usr/lib/cups/filter/brother_lpdwrapper_MFCL2700DW 1 root check 1 "" < /tmp/check.ps > /tmp/check.prn \
  && test -s /tmp/check.prn \
  && grep -q '@PJL' /tmp/check.prn \
  && echo "print filter OK: $(wc -c < /tmp/check.prn) bytes" \
  && rm -f /tmp/check.ps /tmp/check.prn

VOLUME /scans
ENV SAVETO=/scans

EXPOSE 54925/udp
EXPOSE 54925
EXPOSE 54921
EXPOSE 631

ENTRYPOINT ["/usr/bin/docker-entrypoint-brother.sh"]
CMD ["python3", "-m", "brother.supervisor"]
