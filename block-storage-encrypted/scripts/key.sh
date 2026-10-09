#!/bin/sh
validate_key_file() {
  # Keys in this example are 1–1024 single-line printable ASCII bytes.
  # Validate bytes before shell substitution, which otherwise discards newlines/NUL.
  LC_ALL=C od -An -v -tu1 "$1" 2>/dev/null | awk '
    {for(i=1;i<=NF;i++) {n++; if($i<32 || $i>126) bad=1}}
    END {exit (bad || n<1 || n>1024)}' || return 1
  # Kata reserves this prefix for an unseal request in environment transport.
  prefix=$(head -c 7 "$1") || return 1
  [ "$prefix" != 'sealed.' ]
}
