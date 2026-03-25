-- File : someip.lua
-- Who  : Jose Amores (extended, modified by Felix Hirsch)
-- What : SOMEIP dissector

-- bitwise ops helpers
local band,bor = bit.band,bit.bor
local lshift, rshift = bit.lshift,bit.rshift
local tohex = bit.tohex

-- SOME/IP protocol
local SOMEIP_HEADER_OFFSET = 16

local p_my_some_ip_someip = Proto("my_some_ip_someip","my_some_ip SOME/IP Header")

local msg_types = {
    [0]     = "REQUEST",                -- 0x00
    [1]     = "REQUEST_NO_RETURN",      -- 0x01
    [2]     = "NOTIFICATION",           -- 0x02
    [64]    = "REQUEST_ACK",            -- 0x40
    [65]    = "REQUEST_NO_RETURN_ACK",  -- 0x41
    [66]    = "NOTIFICATION_ACK",       -- 0x42
    [128]   = "RESPONSE",               -- 0x80
    [129]   = "ERROR",                  -- 0x81
    [192]   = "RESPONSE_ACK",           -- 0xc0
    [193]   = "ERROR_ACK"               -- 0xc1
}
local ret_codes = {
    [0]     = "E_OK",
    [1]     = "E_NOT_OK",
    [2]     = "E_UNKNOWN_SERVICE",
    [3]     = "E_UNKNOWN_METHOD",
    [4]     = "E_NOT_READY",
    [5]     = "E_NOT_REACHABLE",
    [6]     = "E_TIMEOUT",
    [7]     = "E_WRONG_PROTOCOL_VERSION",
    [8]     = "E_WRONG_INTERFACE_VERSION",
    [9]     = "E_MALFORMED_MESSAGE",
    [10]    = "E_WRONG_MESSAGE_TYPE"
}

local msg_flag = {
	[0]		=	"Method",				-- 0
	[1]		=	"Event"					-- 1
}

local f_msg_id      		= ProtoField.uint32("my_some_ip.someip.messageid","MessageID",base.HEX)
local f_msg_id_service		= ProtoField.uint32("my_some_ip.someip.messageid.srv_id","ServiceID",base.HEX,nil,0xffff0000)
local f_msg_id_flag			= ProtoField.uint32("my_some_ip.someip.messageid.flag","Second ID Type",base.DEC,msg_flag,0x00008000)
local f_msg_id_event		= ProtoField.uint32("my_some_ip.someip.messageid.ev_id","EventID",base.HEX,nil,0x00007fff)
local f_msg_id_method		= ProtoField.uint32("my_some_ip.someip.messageid.methodid","MethodID",base.HEX,nil,0x00007fff)
local f_len         		= ProtoField.uint32("my_some_ip.someip.length","Length",base.HEX)
local f_req_id      		= ProtoField.uint32("my_some_ip.someip.requestid","RequestID",base.HEX)
local f_client_id      		= ProtoField.uint32("my_some_ip.someip.requestid.clientid","ClientID",base.HEX,nil,0xffff0000)
local f_session_id      	= ProtoField.uint32("my_some_ip.someip.requestid.sessionid","SessionID",base.HEX,nil,0x0000ffff)
local f_pv          		= ProtoField.uint8("my_some_ip.someip.protoversion","ProtocolVersion",base.HEX)
local f_iv          		= ProtoField.uint8("my_some_ip.someip.ifaceversion","InterfaceVersion",base.HEX)
local f_mt          		= ProtoField.uint8("my_some_ip.someip.msgtype","MessageType",base.HEX,msg_types)
local f_rc          		= ProtoField.uint8("my_some_ip.someip.returncode","ReturnCode",base.HEX,ret_codes)
local f_pl					= ProtoField.bytes("my_some_ip.someip.payload","Payload")

p_my_some_ip_someip.fields = {f_msg_id,f_msg_id_service,f_msg_id_flag,f_msg_id_event,f_msg_id_method,f_len,f_req_id,f_client_id,f_session_id,f_pv,f_iv,f_mt,f_rc,f_pl}

p_my_some_ip_someip.prefs["udp_port"] = Pref.uint("UDP Port",30490,"UDP Port for SOME/IP")

local my_some_ip_parse_header

-- fields functions
local function my_some_ip_field_msgid(subtree,buf)
    local msg_id = subtree:add(f_msg_id,buf(0,4))
	msg_id:add(f_msg_id_service,buf(0,4))
	msg_id:add(f_msg_id_flag,buf(0,4))
	local id_flag_b = buf(3,1):bitfield(0,1)
	if (id_flag_b) then
		msg_id:add(f_msg_id_event,buf(0,4))
	else
		msg_id:add(f_msg_id_method,buf(0,4))
	end
	
    local msg_id_uint = buf(0,4):uint()

    msg_id:append_text( " ("..tohex(buf(0,2):uint(),4)..
                        ":"..band(rshift(msg_id_uint,15),0x01)..
                        ":"..tohex(band(msg_id_uint,0x7fff),4)..")")

end
local function my_some_ip_field_reqid(subtree,buf)
    local req_id = subtree:add(f_req_id,buf(8,4))
	req_id:add(f_client_id,buf(8,4))
	req_id:add(f_session_id,buf(8,4))
    local req_id_uint = buf(8,4):uint()
    
    req_id:append_text(" ("..buf(8,2)..":"..buf(10,2)..")")
end

-- dissection function
function p_my_some_ip_someip.dissector(buf,pinfo,root)
    pinfo.cols.protocol = "SOME-IP"
	
	-- min size to read length
	--
	if ( buf:len() > 8) then
		local tLen = buf(4,4)
		
		-- check for single someip / someip sd
		--
		if ( buf:len() == (tLen:uint()+8) ) then
			
			-- create subtree
			--
			local subtree = root:add(p_my_some_ip_someip,buf(0,SOMEIP_HEADER_OFFSET))
			my_some_ip_parse_header(subtree,buf(0),pinfo,root)
		end
	end
end

my_some_ip_parse_header = function(subtree,e_buf,pinfo,root)

    -- add protocol fields to subtree
    --

    -- Message ID
	local is_event = my_some_ip_field_msgid(subtree,e_buf)
	
    -- Length
    subtree:add(f_len,e_buf(4,4))
	
	if (e_buf:len() >= 12) then
		-- Requirement ID
		my_some_ip_field_reqid(subtree,e_buf)
	end
	
	if (e_buf:len() >= 16) then
		-- Protocol Version
		subtree:add(f_pv,e_buf(12,1))
		-- Interface Version
		subtree:add(f_iv,e_buf(13,1))

		-- Message type
		subtree:add(f_mt,e_buf(14,1))
		subtree:append_text(" (" ..msg_types[e_buf(14,1):uint()]..")")

		-- Return Code
		subtree:add(f_rc,e_buf(15,1))
	end

	-- SD payload --
	--
	if (e_buf(0,4):uint() == 0xffff8100) and (e_buf:len() > SOMEIP_HEADER_OFFSET)  then
		Dissector.get("my_some_ip_sd"):call(e_buf(SOMEIP_HEADER_OFFSET):tvb(),pinfo,root)
	end
end

-- initialization routine
function p_my_some_ip_someip.init()
    -- register protocol (some ports arount 30490, that is referenced on Specs)
    local udp_dissector_table = DissectorTable.get("udp.port")
    local tcp_dissector_table = DissectorTable.get("tcp.port")
    
    -- Register dissector to multiple ports
    for i,port in ipairs{30490,30491,30501,30502,30503,30504} do
		udp_dissector_table:add(port,p_my_some_ip_someip)
		tcp_dissector_table:add(port,p_my_some_ip_someip)
    end
end

