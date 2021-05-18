All-in-one container that will run a cupsd service as well as set up brscan-skey so that the scanner functions on the panel also work. 

Tested only with:

* MFC-L2700DW

Inspiration for the scripts came from the work here [arjunkc/scanner-scripts](https://github.com/arjunkc/scanner-scripts) which adds the ability to do duplex scanning as well as automatic conversion to pdf. I decided to re-write the scripts so that they are more manageable and work specifically for this container

# Usage

```
# modify .env file to fit your environment
git submodule init && git submodule update
docker run --env-file=.env --net=host -it samsonnguyen/docker-brother-mfc-l27x0dw
```

# Printer

Access the cups server at [http://127.0.0.1:631](http://127.0.0.1:631)

You can print with any cups compatible client connected to this container over port 631/tcp

# Scanner

Use the scanner functions

```
# test the scanner
scanimage -d 'brother4:net1;dev0' -T

# view all available options
docker exec [container] scanimage -d 'brother4:net1;dev0' -h

# This outputs directly to your host
docker exec [container] scanimage --format "tiff" > test.tiff
```

## Scanner Gotchas for skey functions

Need to start the container in host network mode since the printer needs direct access to the eth0 interface

```
 --net=host
```

The printer needs to connect over port `54925/udp`

Configurations and scripts are in `/opt/brother/scanner/brscan-skey`

Scans will go to to the `/scans` volume

## Scanner functions

I've repurposed the modes to suit my own needs

| Scan to mode | duplex | mode | resolution | description |
| --- | --- | --- | --- | --- |
| scantoocr | yes | Black & White | 300 | Quick scanning for OCR purposes |
| scantoemail | yes | Gray[Error Diffusion] | 400 | Higher quality grayscale for OCR purposes | 
| scantoimage | no | 24bit Color | 600 | Higher quality color |
| scantofile | no | Gray[Error Diffusion] | 300 | Non duplex grayscale for OCR purposes |
