#!/usr/bin/bash

##
# Unified SVCB and TLSA record generator for SOME/IP services
# Generates DNS records and SSL certificates for multiple scenarios
##

set -euo pipefail

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="${PROJECT_PATH:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ZONE_FILE=""
CERTIFICATES_PATH=""

INSTANCE_ID="1"
MAJOR_VERSION="0"
MINOR_VERSION="0"
PROTOCOL="UDP"

# Required parameters
CLIENT_ID=""
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
  --client ID               Client ID
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
                            (default: $PROJECT_PATH)
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
    [[ -z "$CLIENT_ID" ]] && missing+=("--client")
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
        --client)
            CLIENT_ID="$2"
            shift 2
            ;;
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
    ZONE_FILE="${PROJECT_PATH}/${SCENARIO}/zones/client.zone"
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
dns_client=$(printf "0x%04x" "$CLIENT_ID")
dns_service=$(printf "0x%04x" "$SERVICE_ID")
dns_instance=$(printf "0x%04x" "$INSTANCE_ID")
dns_major=$(printf "0x%02x" "$MAJOR_VERSION")
dns_minor=$(printf "0x%08x" "$MINOR_VERSION")

# svcb_rdata="ipv4hint=$IP_ADDRESS key65280=$dns_instance  key65281=$dns_major  key65283=$PROTOCOL_ID  key65284=$PORT_NUMBER"
# echo "" >> "$ZONE_FILE"
# echo $(printf "; SVCB records for major=%s instance=%s service=%s id=%s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> "$ZONE_FILE"
# echo $(printf "_someip.major%s.instance%s.service%s.id%s.client.  7200  IN  SVCB  1  .  %s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client" "$svcb_rdata") >> "$ZONE_FILE"

# Generate certificate configuration
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
    IP.1   = ${IP_ADDRESS}
    email.1  = user@example.org"

# Generate certificate
cd "$CERTIFICATES_PATH"
openssl req -config <(echo "$CERTIFICATE_CONF") -new -x509 -sha256 -newkey rsa:2048 -nodes -keyout "${FILE_NAME}.client.key.pem" -days 365 -out "${FILE_NAME}.client.cert.pem" 2>/dev/null

# Append TLSA record to zone file
echo "" >> "$ZONE_FILE"
echo $(printf "; TLSA record for major=%s instance=%s service=%s id=%s\n" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> "$ZONE_FILE"
echo $(printf "_someip.major%s.instance%s.service%s.id%s.client. IN TLSA 3 0 0 (" "$dns_major" "$dns_instance" "$dns_service" "$dns_client") >> "$ZONE_FILE"
openssl x509 -in "${FILE_NAME}.client.cert.pem" -inform PEM -outform DER | xxd -p | sed -E 's/^/    /' >> "$ZONE_FILE"
echo $(printf ")") >> "$ZONE_FILE"

echo "Successfully generated SVCB and TLSA records for client $CLIENT_ID of service $SERVICE_ID"
