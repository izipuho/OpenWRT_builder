-include config.mk

ifndef C
$(error C must be defined)
endif

include $C/config.mk

BUILDDIR := $(shell mktemp --dry-run --directory -t imgbldr-XXXXX)

FILES = ${BUILDDIR}/files
files = files

CACHE = cache/${RELEASE}
DOWNLOADS_BASE = https://downloads.openwrt.org/releases/${RELEASE}/targets/${TARGET}/${SUBTARGET}
INSTRUCTION_SET = $(shell curl --silent ${DOWNLOADS_BASE}/profiles.json | jq --raw-output .arch_packages)

CONFIGS = $(wildcard config.mk) $C/config.mk
DEPS += $(shell [ ! -d ${files} ] || find ${files} -type f,l)
DEPS += $(shell [ -d $C/files ] && find $C/files -type f,l)
DEPS += ${CONFIGS}

IMAGE ?= squashfs-sysupgrade.bin

imagebuilder ?= openwrt-imagebuilder-${RELEASE}-${TARGET}-${SUBTARGET}.Linux-x86_64

ifndef PROFILE
$(error PROFILE must be defined)
endif
image ?= openwrt-${RELEASE}-${TARGET}-${SUBTARGET}-${PROFILE}-${IMAGE}

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

imagebuilder: ${BUILDDIR}/${imagebuilder}

${BUILDDIR}/${imagebuilder}: ${CACHE}/${imagebuilder}.tar.xz ${BUILDDIR}
	tar --touch -C ${BUILDDIR} -xf $<

${CACHE}/${imagebuilder}.tar.xz: | ${CACHE}
	curl --remote-name --continue-at - --output-dir $| ${DOWNLOADS_BASE}/${@F}

image: $C/${image}

${FILES}:
	mkdir ${FILES}
	${FILES_INSTALL}
	[ ! -d $C/files ] || cp -r -T -f $C/files ${FILES}

files: ${FILES}


$C/${image}: ${BUILDDIR}/${imagebuilder} ${FILES} ${DEPS}
	umask 022; $(MAKE) -C $< image \
		PROFILE=${PROFILE} \
		PACKAGES="${PACKAGES}" \
		FILES=${FILES} \
		CONFIG_DOWNLOAD_FOLDER=$(realpath ${CACHE})/${INSTRUCTION_SET}
	cp ${BUILDDIR}/${imagebuilder}/bin/targets/${TARGET}/${SUBTARGET}/${image} $@
ifndef LEAVE_BUILD
	rm -rf ${BUILDDIR}
else
	@echo ${BUILDDIR}
endif

.PHONY: listpks image
.SECONDARY: ${BUILDDIR} ${BUILDDIR}/${imagebuilder} ${FILES}
