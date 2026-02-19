-include config.mk

ifndef C
$(error C must be defined)
endif

include $C/config.mk

BUILDDIR := $(shell mktemp -d -t imgbldr.XXXXXX 2>/dev/null || mktemp -d /tmp/imgbldr.XXXXXX)
BUILDDIR_HINT_FILE ?= $C/.imgbuilder_builddir

FILES = ${BUILDDIR}/files
files = files

CACHE = cache/${RELEASE}
DOWNLOADS_BASE = https://downloads.openwrt.org/releases/${RELEASE}/targets/${TARGET}/${SUBTARGET}
INSTRUCTION_SET = $(shell curl --silent ${DOWNLOADS_BASE}/profiles.json | jq --raw-output .arch_packages)

CONFIGS = $(wildcard config.mk) $C/config.mk
DEPS += $(shell [ ! -d ${files} ] || find ${files} -type f,l)
DEPS += $(shell [ -d $C/files ] && find $C/files -type f,l)
DEPS += ${CONFIGS}

imagebuilder ?= openwrt-imagebuilder-${RELEASE}-${TARGET}-${SUBTARGET}.Linux-x86_64

ifndef PROFILE
$(error PROFILE must be defined)
endif

IMAGES ?= sysupgrade
INVALID_IMAGES := $(filter-out sysupgrade factory,$(IMAGES))
ifneq ($(strip $(INVALID_IMAGES)),)
$(error unsupported IMAGES: $(INVALID_IMAGES))
endif

image_name = openwrt-${RELEASE}-${TARGET}-${SUBTARGET}-${PROFILE}-squashfs-$(1).bin
OUT_IMAGES := $(foreach kind,$(IMAGES),$(call image_name,$(kind)))

PACKAGES_INCLUDE ?=
PACKAGES_EXCLUDE ?=
PACKAGES := $(addprefix -,${PACKAGES_EXCLUDE}) ${PACKAGES_INCLUDE}

all: image

listpks:
	@echo ${PACKAGES}

${CACHE}:
	mkdir --parents $@

${BUILDDIR}:
	mkdir --parents $@
	printf '%s\n' "$@" > ${BUILDDIR_HINT_FILE}

imagebuilder: ${BUILDDIR}/${imagebuilder}

${BUILDDIR}/${imagebuilder}: ${CACHE}/${imagebuilder}.tar.xz ${BUILDDIR}
	tar -C ${BUILDDIR} -xf $<

${CACHE}/${imagebuilder}.tar.xz: | ${CACHE}
	curl --remote-name --continue-at - --output-dir $| ${DOWNLOADS_BASE}/${@F}

image: ${OUT_IMAGES:%=$C/%}

${FILES}:
	mkdir ${FILES}
	${FILES_INSTALL}
	[ ! -d $C/files ] || cp -r -T -f $C/files ${FILES}

files: ${FILES}


$C/.images-built: ${BUILDDIR}/${imagebuilder} ${FILES} ${DEPS}
	umask 022; $(MAKE) -C $< image \
		PROFILE=${PROFILE} \
		PACKAGES="${PACKAGES}" \
		FILES=${FILES} \
		CONFIG_DOWNLOAD_FOLDER=$(realpath ${CACHE})/${INSTRUCTION_SET}
	@set -e; \
	for kind in ${IMAGES}; do \
		name="$(call image_name,$$kind)"; \
		cp ${BUILDDIR}/${imagebuilder}/bin/targets/${TARGET}/${SUBTARGET}/$$name $C/$$name; \
	done
	touch $@
ifndef LEAVE_BUILD
	rm -rf ${BUILDDIR}
	rm -f ${BUILDDIR_HINT_FILE}
else
	@echo ${BUILDDIR}
endif

$C/${OUT_IMAGES}: $C/.images-built

.PHONY: listpks image
.SECONDARY: ${BUILDDIR} ${BUILDDIR}/${imagebuilder} ${FILES}
