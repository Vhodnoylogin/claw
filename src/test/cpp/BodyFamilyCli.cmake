# Black-box setup diagnostics: parser tests alone cannot establish CLI behaviour.
file(MAKE_DIRECTORY "${FIXTURE_DIR}")
set(catalog "${FIXTURE_DIR}/MorphLinks.xml")
set(bindings "${FIXTURE_DIR}/BodyFamilyBindings.xml")
set(input "${FIXTURE_DIR}/models.txt")
file(WRITE "${catalog}" [=[<MorphLinkProfiles schemaVersion="1">
  <Defaults male="M" female="F"/>
  <Profile id="M" family="Vanilla" version="1" sex="male" calibration="test"><Rule source="$actor.weight" target="CLAWArmGirth" gain="1" cap="1"/></Profile>
  <Profile id="F" family="CBBE" version="1" sex="female" calibration="test"><Rule source="$actor.weight" target="CLAWArmGirth" gain="1" cap="1"/></Profile>
  <Profile id="B" family="BHUNP" version="1" sex="female" calibration="test"><Rule source="$actor.weight" target="CLAWArmGirth" gain="0.5" cap="1"/></Profile>
</MorphLinkProfiles>]=])
file(WRITE "${bindings}" [=[<BodyFamilyBindings schemaVersion="1">
  <Bind sex="female" mesh="actors/follower/body_1.nif" profile="B"/>
  <Bind sex="female" mesh="actors/other/body_1.nif" profile="F"/>
</BodyFamilyBindings>]=])
function(check label models sex code expected)
    file(WRITE "${input}" "${models}")
    execute_process(COMMAND "${TOOL}" body-family "${catalog}" "${bindings}" "${sex}" ${ARGN}
        INPUT_FILE "${input}" RESULT_VARIABLE actual OUTPUT_VARIABLE output ERROR_VARIABLE error TIMEOUT 10)
    if(NOT "${actual}" STREQUAL "${code}" OR NOT "${output}${error}" MATCHES "${expected}")
        message(FATAL_ERROR "${label}: exit=${actual}; stdout=${output}; stderr=${error}")
    endif()
endfunction()
check(mapped "Meshes\\ACTORS\\Follower\\BODY_1.NIF\n" female 0 [=["reason":"skin-binding","blocked":false,"profile":"B"]=])
check(unmapped "actors/unmapped/body.nif\n" female 0 [=["reason":"default","blocked":false,"profile":"F"]=])
check(male "actors/follower/body_1.nif\n" male 0 [=["profile":"M"]=])
check(ambiguous "actors/follower/body_1.nif\nactors/other/body_1.nif\n" female 2 [=["reason":"ambiguous","blocked":true,"profile":null]=])
check(unobserved "" female 0 [=["sourceObserved":false.*"profile":"F"]=] --source-unobserved)
check(invalid-path "../body.nif\n" female 2 "relative naked-skin NIF paths")
check(unobserved-with-path "actors/follower/body_1.nif\n" female 2 "no paths for an unobserved source" --source-unobserved)
file(RENAME "${bindings}" "${bindings}.saved")
check(missing-optional-file "actors/follower/body_1.nif\n" female 0 [=["reason":"default","blocked":false,"profile":"F"]=])
file(RENAME "${bindings}.saved" "${bindings}")
file(READ "${catalog}" xml)
string(REPLACE "<Defaults male=\"M\" female=\"F\"/>" "" xml "${xml}")
file(WRITE "${catalog}" "${xml}")
check(no-default "actors/unmapped/body.nif\n" female 2 [=["reason":"default","blocked":false,"profile":null]=])
file(WRITE "${bindings}" "damaged-prefix<BodyFamilyBindings schemaVersion=\"1\"/>")
check(invalid-document "" female 2 "Unexpected content outside body bindings root")
