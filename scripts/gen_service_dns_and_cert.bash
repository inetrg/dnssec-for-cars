#!/usr/bin/bash

##
# Unified SVCB and TLSA record generator for SOME/IP services
# Generates DNS records and SSL certificates for multiple scenarios
##

set -euo pipefail

# Default values
PROJECT_PATH="${PROJECT_PATH:-/home/vm-user/workspace/mininet-vsomeip-evaluation}"
ZONE_FILE=""
CERTIFICATES_PATH=""

INSTANCE_ID="1"
MAJOR_VERSION="0"
MINOR_VERSION="0"
PROTOCOL="UDP"

# Required parameters
SERVICE_ID=""
IP_ADDRESS=""
PORT_NUMBER=""
FILE_NAME=""
SCENARIO=""

# Parsed protocol number
PROTOCOL_ID=""

printUsage() {
    cat << EOF
Unified SVCB and TLSA record generator for SOME/IP services.

Usage: $0 [OPTIONS]

Required Options:
  --service ID              Service ID
  --ip ADDRESS              IP address
  --port PORT               Port number
  --file-name NAME          Output file name (without extension)
                            , used for names of cert and key files
  --scenario NAME           Scenario: carnet or scalability

Optional Options:
  --major-version VERSION   Major version (default: 0)
  --minor-version VERSION   Minor version (default: 0)
  --instance ID             Instance ID (default: 1)
  --protocol PROTO          Protocol: UDP (default) or TCP
  --project-path PATH       Project root path
                            (default: /home/vm-user/workspace/mininet-vsomeip-evaluation)
  --zone-file PATH          Path to zone file to append records
                            (default: \$PROJECT_PATH/\$SCENARIO/zones/service.zone)
  --certificates-path PATH  Path to certificates directory
                            (default: \$PROJECT_PATH/\$SCENARIO/certificates)
  --help                    Show this usage message

Example:
  $0 --service 1 --instance 2 --ip 172.17.0.3 --port 30509 --file-name h1 --scenario carnet
EOF
    exit 1
}

parseProtocol() {
    case "$1" in
        'UDP')
            echo 17
            ;;
        'TCP')
            echo 6
            ;;
        *)
            echo "Error: Unsupported protocol '$1'. Use UDP or TCP." >&2
            exit 1
            ;;
    esac
}

validateRequired() {
    local missing=()
    [[ -z "$SERVICE_ID" ]] && missing+=("--service")
    [[ -z "$IP_ADDRESS" ]] && missing+=("--ip")
    [[ -z "$PORT_NUMBER" ]] && missing+=("--port")
    [[ -z "$FILE_NAME" ]] && missing+=("--file-name")
    [[ -z "$SCENARIO" ]] && missing+=("--scenario")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Error: Missing required options: ${missing[*]}" >&2
        printUsage
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --service)
            SERVICE_ID="$2"
            shift 2
            ;;
        --instance)
            INSTANCE_ID="$2"
            shift 2
            ;;
        --major-version)
            MAJOR_VERSION="$2"
            shift 2
            ;;
        --minor-version)
            MINOR_VERSION="$2"
            shift 2
            ;;
        --ip)
            IP_ADDRESS="$2"
            shift 2
            ;;
        --port)
            PORT_NUMBER="$2"
            shift 2
            ;;
        --protocol)
            PROTOCOL="$2"
            shift 2
            ;;
        --file-name)
            FILE_NAME="$2"
            shift 2
            ;;
        --project-path)
            PROJECT_PATH="$2"
            shift 2
            ;;
        --scenario)
            SCENARIO="$2"
            shift 2
            ;;
        --zone-file)
            ZONE_FILE="$2"
            shift 2
            ;;
        --certificates-path)
            CERTIFICATES_PATH="$2"
            shift 2
            ;;
        --help)
            printUsage
            ;;
        *)
            echo "Error: Unknown option '$1'" >&2
            printUsage
            ;;
    esac
done

# Validate required parameters
validateRequired

# Set derived defaults if not provided
if [[ -z "$ZONE_FILE" ]]; then
    ZONE_FILE="${PROJECT_PATH}/${SCENARIO}/zones/service.zone"
fi

if [[ -z "$CERTIFICATES_PATH" ]]; then
    CERTIFICATES_PATH="${PROJECT_PATH}/${SCENARIO}/certificates"
fi

# Verify paths exist
if [[ ! -d "$(dirname "$ZONE_FILE")" ]]; then
    echo "Error: Zone file directory does not exist: $(dirname "$ZONE_FILE")" >&2
    exit 1
fi

if [[ ! -d "$CERTIFICATES_PATH" ]]; then
    echo "Error: Certificates directory does not exist: $CERTIFICATES_PATH" >&2
    exit 1
fi

# Parse protocol
PROTOCOL_ID=$(parseProtocol "$PROTOCOL")

# Convert IDs to hex format for DNS
dns_service=$(printf "0x%04x" "$SERVICE_ID")
dns_instance=$(printf "0x%04x" "$INSTANCE_ID")
dns_major=$(printf "0x%02x" "$MAJOR_VERSION")
dns_minor=$(printf "0x%08x" "$MINOR_VERSION")

# Generate SVCB rdata
svcb_rdata="ipv4hint=$IP_ADDRESS  port=$PORT_NUMBER  key65280=$dns_instance  key65281=$dns_major  key65282=$dns_minor  key65283=$PROTOCOL_ID"

# Append SVCB records to zone file
echo "" >> "$ZONE_FILE"
echo $(printf "; SVCB records for minor=%s major=%s instance=%s id=%s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> "$ZONE_FILE"
echo $(printf "_someip.minor%s.major%s.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"
echo $(printf "_someip.major%s.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_instance" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"
echo $(printf "_someip.minor%s.major%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_minor" "$dns_major" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"
echo $(printf "_someip.instance%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_instance" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"
echo $(printf "_someip.major%s.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"
echo $(printf "_someip.id%s.service.  7200  IN  SVCB  1  .  %s\n" "$dns_service" "$svcb_rdata") >> "$ZONE_FILE"

# Generate certificate configuration
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
    IP.1   = ${IP_ADDRESS}
    email.1  = user@example.org"

# Generate certificate
cd "$CERTIFICATES_PATH"
openssl req -config <(echo "$CERTIFICATE_CONF") -new -x509 -sha256 -newkey rsa:2048 -nodes -keyout "${FILE_NAME}.service.key.pem" -days 365 -out "${FILE_NAME}.service.cert.pem" 2>/dev/null

# Append TLSA record to zone file
echo "" >> "$ZONE_FILE"
echo $(printf "; TLSA record for minor=%s major=%s instance=%s id=%s\n" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> "$ZONE_FILE"
echo $(printf "_someip.minor%s.major%s.instance%s.id%s.service. IN TLSA 3 0 0 (" "$dns_minor" "$dns_major" "$dns_instance" "$dns_service") >> "$ZONE_FILE"
openssl x509 -in "${FILE_NAME}.service.cert.pem" -inform PEM -outform DER | xxd -p | sed -E 's/^/    /' >> "$ZONE_FILE"
echo $(printf ")") >> "$ZONE_FILE"

echo "Successfully generated SVCB and TLSA records for service $SERVICE_ID"
