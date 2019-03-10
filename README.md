Docker container for setting up a cups server with drivers for Brother-L2700DW multi-function printers.

Usage
===
```
docker run -e PRINTER_NAME='Brother-MFC-L2700DW' -e PRINTER_IP='10.10.10.1' -p 631:631 -p 54925:54925/udp -it samsonnguyen/docker-brother-mfc-l27x0dw
```

Access the cups server at http://127.0.0.1:631

Printer
===

You can print with any cups compatible client

Scanner
===

Use the scanner functions

```
# test the scanner
scanimage -d 'brother4:net1;dev0' -T

# view all available options
docker exec [container] scanimage -d 'brother4:net1;dev0' -h

# This outputs directly to your host
docker exec [container] scanimage --format "tiff" > test.tiff
```
