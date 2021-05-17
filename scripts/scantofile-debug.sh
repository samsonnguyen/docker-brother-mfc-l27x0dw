#! /bin/bash
#
set +o noclobber
set -x
#
#   Modified from https://github.com/arjunkc/scanner-scripts
#
#   $1 = scanner device
#   $2 = brother internal
#   
#       100,200,300,400,600
#
#   This is my batch scan. It scans double sided pages by default.
#   query device with scanimage -h to get allowed resolutions
#   Will scan from the 'brother4:net1;dev0' scanner by default.

scan_resolution=${SCAN_RESOLUTION:-"300"}
scan_width=${SCAN_WIDTH:-"215.88"}
scan_height=${SCAN_HEIGHT:-"279.4"}
scan_mode=${SCAN_MODE:-"Black & White"}
scan_source=${SCAN_SOURCE:-"Automatic Document Feeder(left aligned,Duplex)"}
epochnow="1621289310"
fileprefix='scantofile'
brscan_skey_install_dir='/opt/brother/scanner/brscan-skey/'
saveto=${SAVETO:-"/scans"}

( set -o posix ; set ) >> /dev/stdout

exec ruby ${brscan_skey_install_dir}/script/batchscan.rb \
    --outputdir ${SAVETO} \
    --prefix ${fileprefix} \
    --timestamp ${epochnow} \
    --resolution ${scan_resolution} \
    --height $scan_height \
    --width $scan_width \
    --mode "$scan_mode" \
    --source "$scan_source" \
    --duplex "false" 
