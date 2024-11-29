#!/usr/bin/bash

printUsage() {
    printf "This tool generates svcb and tlsa entries for SOME/IP services.\n"
    printf "Usage: $0 <service id> <instance id> <major version> <minor version> <ip address> <port> <protocol> <file name>\n"
    printf "Example: $0 1 2 3 4 172.17.0.3 30509 UDP h1\n"
}

if [[ $# -gt 7 ]]; then
    PROJECT_FOLDER_PATH="/home/vm-user/workspace/mininet-vsomeip-evaluation"
    ZONE_FILE_PATH="${PROJECT_FOLDER_PATH}/zones/service.zone"
    CERTIFICATES_FOLDER_PATH="${PROJECT_FOLDER_PATH}/certificates"
    service_id=$1
    instance_id=$2
    major_version=$3
    minor_version=$4
    ip_address=$5
    port_number=$6
    protocol_id=$7
    file_name=$8

    case $protocol_id in
        'UDP')
             protocol_id=17
             ;;
        'TCP')
             protocol_id=6
             ;;
        *)
            printf "Not supported protocol number.\n"
            exit 1
    esac

    #printf "service id: %s\n" "$service_id"
    #printf "instance id: %s\n" "$instance_id"
    #printf "major version: %s\n" "$major_version"
    #printf "minor version: %s\n" "$minor_version"

    dns_service=$(printf "0x%04x" $service_id)
    dns_instance=$(printf "0x%04x" $instance_id)
    dns_major=$(printf "0x%02x" $major_version)
    dns_minor=$(printf "0x%08x" $minor_version)

    svcb_rdata="ipv4hint=$ip_address  port=$port_number  key65280=$dns_instance  key65281=$dns_major  key65282=$dns_minor  key65283=$protocol_id"
    echo $(printf "; SVCB records for minor=%s major=%s instance=%s id=%s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> $ZONE_FILE_PATH
    echo $(printf "_someip.minor%s.major%s.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.major%s.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_instance" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.minor%s.major%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_minor" "$dns_major" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_instance" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.major%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_service" "$svcb_rdata") >> $ZONE_FILE_PATH


    CERTIFICATE_CONF="[ req ]
    prompt               = no
    default_bits         = 2048
    default_keyfile      = server-key.pem
    distinguished_name   = subject
    req_extensions       = req_ext
    x509_extensions      = x509_ext
    string_mask          = utf8only

    [ subject ]
    countryName          = XX
    stateOrProvinceName  = XX
    localityName         = City
    organizationName     = Example Org
    commonName           = Example
    emailAddress         = user@example.org

    [ x509_ext ]
    subjectKeyIdentifier    = hash
    authorityKeyIdentifier  = keyid,issuer
    basicConstraints        = critical,CA:FALSE
    keyUsage                = digitalSignature, keyEncipherment
    extendedKeyUsage        = clientAuth, serverAuth, secureShellServer
    subjectAltName          = @alternate_names
    nsComment               = \"OpenSSL Generated Certificate\"

    [ req_ext ]
    subjectKeyIdentifier    = hash
    basicConstraints        = critical,CA:FALSE
    keyUsage                = digitalSignature, keyEncipherment
    extendedKeyUsage        = clientAuth, serverAuth, secureShellServer
    subjectAltName          = @alternate_names
    nsComment               = \"OpenSSL Generated Certificate\"

    [ alternate_names ]
    DNS.1  = $(printf "_someip.minor%s.major%s.instance%s.id%s.service." "$dns_minor" "$dns_major" "$dns_instance" "$dns_service")
    DNS.2  = $(printf "_someip.major%s.instance%s.id%s.service."         "$dns_major" "$dns_instance" "$dns_service")
    DNS.3  = $(printf "_someip.minor%s.major%s.id%s.service."            "$dns_minor" "$dns_major" "$dns_service")
    DNS.4  = $(printf "_someip.instance%s.id%s.service."                 "$dns_instance" "$dns_service")
    DNS.5  = $(printf "_someip.major%s.id%s.service."                    "$dns_major" "$dns_service")
    DNS.6  = $(printf "_someip.id%s.service."                            "$dns_service")
    IP.1   = ${ip_address}
    email.1  = user@example.org"

    cd ${CERTIFICATES_FOLDER_PATH}
    openssl req -config <(echo "$CERTIFICATE_CONF") -new -x509 -sha256 -newkey rsa:2048 -nodes -keyout "${file_name}.service.key.pem" -days 365 -out "${file_name}.service.cert.pem" 2>/dev/null

    echo $(printf "; TLSA record for minor=%s major=%s instance=%s id=%s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> $ZONE_FILE_PATH
    echo $(printf "_someip.minor%s.major%s.instance%s.id%s.service. IN TLSA 3 0 0 (" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> $ZONE_FILE_PATH
    openssl x509 -in "${file_name}.service.cert.pem" -inform PEM -outform DER | xxd -p | sed -E 's/^/    /' >> $ZONE_FILE_PATH
    echo $(printf ")") >> $ZONE_FILE_PATH
else
    printUsage
fi