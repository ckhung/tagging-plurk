#!/bin/sh
cut -d' ' -f 2- *.txt | grep -v '^ *$' | perl -pe 's/ +/\n/g' | sort | uniq -c | sort -nr > stat.txt
