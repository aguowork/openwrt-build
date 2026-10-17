#!/usr/bin/env bash
# 只处理当前固件使用的包。设备补丁放在 patches/source/，运行时文件放在 files/。
set -Eeuo pipefail
: "${RECIPE_ROOT:?}" "${SOURCE_DIR:?}" "${PLATFORM:?}" "${DEVICE:?}"
cd "$SOURCE_DIR"

for scope in common "$PLATFORM" "$DEVICE"; do
    patch_dir="$RECIPE_ROOT/patches/source/$scope"
    [[ -d $patch_dir ]] || continue
    while IFS= read -r patch_file; do
        if git apply --check "$patch_file"; then
            git apply "$patch_file"
        elif git apply --reverse --check "$patch_file"; then
            echo "上游已包含补丁：${patch_file##*/}"
        else
            echo "补丁与上游不再匹配，请更新：$patch_file" >&2
            exit 1
        fi
    done < <(find "$patch_dir" -maxdepth 1 -name '*.patch' -type f | LC_ALL=C sort)
done

# 保持原固件的包选择和 Argon 主题；不引入上游的额外预装套件。
sed -i '/^DEFAULT_PACKAGES += $(DEFAULT_PACKAGES.tweak)$/d' include/target.mk
sed -i 's/libustream-mbedtls/libustream-openssl/g' include/target.mk
find feeds/luci/collections -name Makefile -type f -exec sed -i \
    -e 's/luci-theme-bootstrap/luci-theme-argon/g' -e '/luci-app-attendedsysupgrade/d' {} +

# 兼容旧版 package-metadata 的虚拟包递归依赖写法，新版不会命中。
sed -i 's/<PACKAGE_$pkgname/!=y/g' scripts/package-metadata.pl
wechat=custom/luci-app-wechatpush/Makefile
sed -i \
    -e 's/^config PACKAGE_$(PKG_NAME)_Local_Disk_Information_Detection$/config PACKAGE_$(PKG_NAME)_Enable_Local_Disk_Information_Detection/' \
    -e 's/^config PACKAGE_$(PKG_NAME)_Host_Information_Detection$/config PACKAGE_$(PKG_NAME)_Enable_Host_Information_Detection/' "$wechat"

sed -i -e "s/record_enable '1'/record_enable '0'/g" \
    -e "s/disable_hnat '1'/disable_hnat '0'/g" \
    -e "s/auto_load_engine '1'/auto_load_engine '0'/g" \
    custom/open-app-filter/files/appfilter.config
oaf_defaults=custom/luci-app-oaf/root/etc/uci-defaults/94_feature_3.0
[[ ! -f $oaf_defaults ]] || sed -i '/\(disable_hnat\|auto_load_engine\)/d' "$oaf_defaults"
sed -i '/dns_redirect/d' package/network/services/dnsmasq/files/dhcp.conf

if [[ -f package/system/opkg/Makefile ]]; then
    install -Dm644 "$RECIPE_ROOT/patches/packages/opkg/001-fix-provides-version-parsing.patch" \
        package/system/opkg/patches/001-fix-provides-version-parsing.patch
fi
install -Dm644 "$RECIPE_ROOT/patches/packages/miniupnpd/999-default-leaseduration.patch" \
    feeds/packages/net/miniupnpd/patches/999-default-leaseduration.patch

if [[ -f package/libs/openssl/Config.in ]] && grep -q 'select PACKAGE_kmod-tls' package/libs/openssl/Config.in; then
    sed -i '/select PACKAGE_kmod-tls/c\	depends on PACKAGE_kmod-tls\n\tdefault y if PACKAGE_kmod-tls' \
        package/libs/openssl/Config.in
fi

if [[ ${INCLUDE_PASSWALL:-false} == true ]]; then
    rules=custom/luci-app-passwall/root/usr/share/passwall/rules/chnlist
    [[ ! -f $rules ]] || : > "$rules"
    xray=custom/luci-app-passwall/luasrc/passwall/util_xray.lua
    [[ ! -f $xray ]] || sed -i -e 's/maxRTT = "1s"/maxRTT = "2s"/g' \
        -e 's/sampling = 3/sampling = 5/g' "$xray"
    rust=feeds/packages/lang/rust/Makefile
    [[ ! -f $rust ]] || sed -i 's/download-ci-llvm=true/download-ci-llvm=false/g' "$rust"
    geodata=custom/v2ray-geodata/Makefile
    version=$(sed -n 's/^GEOIP_VER:=\([0-9]*\)$/\1/p' "$geodata")
    if [[ -n $version ]]; then
        url="https://github.com/v2fly/geoip/releases/download/$version"
        old_hash=$(curl --fail --location --retry 3 "$url/geoip.dat.sha256sum" | awk '{print $1}')
        new_hash=$(curl --fail --location --retry 3 "$url/geoip-only-cn-private.dat.sha256sum" | awk '{print $1}')
        [[ $old_hash =~ ^[a-fA-F0-9]{64}$ && $new_hash =~ ^[a-fA-F0-9]{64}$ ]]
        sed -i -e 's/=geoip\.dat/=geoip-only-cn-private.dat/g' -e "s/$old_hash/$new_hash/g" "$geodata"
    fi
fi

if [[ $PLATFORM == nss ]]; then
    target_mk=target/linux/qualcommax/Makefile
    sed -i -e 's/ automount / /g' -e 's/ cpufreq / /g' \
        -e 's/wpad-openssl/wpad-mesh-openssl/g' \
        -e '/^[[:space:]]*kmod-qca-nss-drv-\(eogremgr\|gre\|map-t\|match\|mirror\|tun6rd\|tunipip6\|vxlanmgr\|wifi-meshmgr\)\([[:space:]]\|$\)/d' \
        -e '/^[[:space:]]*kmod-qca-nss-macsec\([[:space:]]\|$\)/d' "$target_mk"
    sed -i 's/ kmod-qca-nss-crypto//g' target/linux/qualcommax/ipq807x/target.mk
    find target/linux/qualcommax -type f \( -name set-irq-affinity -o -name smp_affinity \) -delete
    defaults=target/linux/qualcommax/base-files/etc/uci-defaults
    [[ ! -d $defaults ]] || find "$defaults" -maxdepth 1 -type f -name '99*.sh' -delete

    # LiBwrt 与旧项目一样使用 DD-WRT ath11k 固件；固定来源提交，避免第二次追随 main。
    firmware_mk=package/firmware/ath11k-firmware/Makefile
    if ! grep -q 'define Package/ath11k-firmware-ipq8074-ddwrt' "$firmware_mk"; then
        firmware_commit=63c7fdb3c9685d9f497d6128d9280a772f77562d
        firmware_url="https://raw.githubusercontent.com/VIKINGYFY/immortalwrt/$firmware_commit/$firmware_mk"
        curl --fail --location --retry 3 --output "$firmware_mk" "$firmware_url"
        printf 'source-file\tath11k-firmware\t%s\t%s\t%s\n' "$firmware_url" "$firmware_commit" "$firmware_commit" \
            >> "$RECIPE_ROOT/.work/sources.lock"
    fi
    sed -i 's/ath11k-firmware-ipq8074\([[:space:]]\|$\)/ath11k-firmware-ipq8074-ddwrt\1/g' \
        target/linux/qualcommax/ipq807x/target.mk

    pbuf=package/kernel/mac80211/files/pbuf.uci
    [[ ! -f $pbuf ]] || sed -i -e "s/auto_scale '1'/auto_scale 'off'/g" \
        -e "s/scaling_governor 'performance'/scaling_governor 'schedutil'/g" "$pbuf"
    find package feeds -type f -name qca-nss-drv.init -exec sed -i 's/^START=.*/START=88/' {} +
    pbuf_init=package/kernel/mac80211/files/qca-nss-pbuf.init
    [[ ! -f $pbuf_init ]] || sed -i 's/^START=.*/START=89/' "$pbuf_init"
fi

echo '源码定制完成。'
