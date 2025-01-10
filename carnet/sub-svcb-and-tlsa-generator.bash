#!/usr/bin/bash

printUsage() {
    printf "This tool generates svcb and tlsa entries for SOME/IP clients.\n"
    printf "Usage: $0 <client id> <service id> <instance id> <major version> <ip address> <ports> <protocol> <file name>\n"
    printf "Example: $0 1 2 3 4 172.17.0.3 40000,40002 UDP h2\n"
}

if [[ $# -gt 7 ]]; then
    PROJECT_FOLDER_PATH="/home/vm-user/workspace/mininet-vsomeip-evaluation"
    SCENARIO_FOLDER_PATH="${PROJECT_FOLDER_PATH}/carnet"
    ZONE_FILE_PATH="${SCENARIO_FOLDER_PATH}/zones/client.zone"
    CERTIFICATES_FOLDER_PATH="${SCENARIO_FOLDER_PATH}/certificates"
    client_id=$1
    service_id=$2
    instance_id=$3
    major_version=$4
    ip_address=$5
    port_numbers=$6
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

    dns_client=$(printf "0x%04x" $client_id)
    dns_service=$(printf "0x%04x" $service_id)
    dns_instance=$(printf "0x%04x" $instance_id)
    dns_major=$(printf "0x%02x" $major_version)

    svcb_rdata="ipv4hint=$ip_address key65280=$dns_instance  key65281=$dns_major  key65283=$protocol_id  key65284=$port_numbers"
    echo $(printf "; SVCB records for major=%s instance=%s service=%s id=%s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> $ZONE_FILE_PATH
    echo $(printf "_someip.major%s.instance%s.service%s.id%s.client.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.instance%s.service%s.id%s.client.  7200  IN  SVCB  1  .  %s\n" "$dns_instance" "$dns_service" "$dns_client" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.major%s.service%s.id%s.client.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_service" "$dns_client" "$svcb_rdata") >> $ZONE_FILE_PATH
    echo $(printf "_someip.service%s.id%s.client.  7200  IN  SVCB  1  .  %s\n" "$dns_service" "$dns_client" "$svcb_rdata") >> $ZONE_FILE_PATH


    CERTIFICATE_CONF="[ req ]
    prompt               = no
    default_bits         = 2048
    default_keyfile      = client-key.pem
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
    DNS.1  = $(printf "_someip.major%s.instance%s.service%s.id%s.client."         "$dns_major" "$dns_instance" "$dns_service" "$dns_client")
    DNS.2  = $(printf "_someip.instance%s.service%s.id%s.client."                 "$dns_instance" "$dns_service" "$dns_client")
    DNS.3  = $(printf "_someip.major%s.service%s.id%s.client."                    "$dns_major" "$dns_service" "$dns_client")
    DNS.4  = $(printf "_someip.service%s.id%s.client."                            "$dns_service" "$dns_client")
    IP.1   = ${ip_address}
    email.1  = user@example.org"

    cd ${CERTIFICATES_FOLDER_PATH}
    openssl req -config <(echo "$CERTIFICATE_CONF") -new -x509 -sha256 -newkey rsa:2048 -nodes -keyout "${file_name}.client.key.pem" -days 365 -out "${file_name}.client.cert.pem" 2>/dev/null

    echo $(printf "; TLSA record for major=%s instance=%s service=%s id=%s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> $ZONE_FILE_PATH
    echo $(printf "_someip.major%s.instance%s.service%s.id%s.client. IN TLSA 3 0 0 (" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> $ZONE_FILE_PATH
    openssl x509 -in "${file_name}.client.cert.pem" -inform PEM -outform DER | xxd -p | sed -E 's/^/    /' >> $ZONE_FILE_PATH
    echo $(printf ")") >> $ZONE_FILE_PATH
else
    printUsage
fi