ifeq ($(strip $(DEVKITPRO)),)
$(error "Please set DEVKITPRO to the devkitPro installation directory")
endif

TOPDIR ?= $(CURDIR)
include $(DEVKITPRO)/libnx/switch_rules

TARGET      := nx_pctl_runtime_probe
PROGRAM_ID  := 4200000000F04354
BUILD       := build
SOURCES     := source
INCLUDES    := include

ARCH        := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS      := -g -Wall -Wextra -O2 -ffunction-sections $(ARCH) $(DEFINES)
CFLAGS      += $(INCLUDE) -D__SWITCH__
ASFLAGS     := -g $(ARCH)
LDFLAGS     := -specs=$(DEVKITPRO)/libnx/switch.specs -g $(ARCH) -Wl,-Map,$(notdir $*.map)
LIBS        := -lnx
LIBDIRS     := $(PORTLIBS) $(LIBNX)

ifneq ($(BUILD),$(notdir $(CURDIR)))

export OUTPUT   := $(CURDIR)/$(TARGET)
export TOPDIR   := $(CURDIR)
export VPATH    := $(foreach dir,$(SOURCES),$(CURDIR)/$(dir))
export DEPSDIR  := $(CURDIR)/$(BUILD)
export APP_JSON := $(TOPDIR)/$(TARGET).json
export LD       := $(CC)

CFILES          := $(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
export OFILES   := $(CFILES:.c=.o)
export INCLUDE  := $(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) \
                   $(foreach dir,$(LIBDIRS),-I$(dir)/include) \
                   -I$(CURDIR)/$(BUILD)
export LIBPATHS := $(foreach dir,$(LIBDIRS),-L$(dir)/lib)

.PHONY: all package clean $(BUILD)

all: $(BUILD)

$(BUILD):
	@[ -d $@ ] || mkdir -p $@
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile

package: all
	@mkdir -p out/atmosphere/contents/$(PROGRAM_ID)/flags
	@cp $(TARGET).nsp out/atmosphere/contents/$(PROGRAM_ID)/exefs.nsp
	@touch out/atmosphere/contents/$(PROGRAM_ID)/flags/boot2.flag
	@cd out && zip -qr ../$(TARGET).zip atmosphere

clean:
	@rm -rf $(BUILD) out $(TARGET).elf $(TARGET).nso $(TARGET).npdm \
		$(TARGET).nsp $(TARGET).zip

else

DEPENDS := $(OFILES:.o=.d)

.PHONY: all
all: $(OUTPUT).nsp

$(OUTPUT).nsp: $(OUTPUT).nso $(OUTPUT).npdm
$(OUTPUT).nso: $(OUTPUT).elf
$(OUTPUT).elf: $(OFILES)

-include $(DEPENDS)

endif
