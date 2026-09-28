import 'package:flutter_test/flutter_test.dart';
import 'package:geofatali/models/models.dart';

void main() {
  group('parsing what the server sends', () {
    test('a calculated bearing capacity', () {
      final result = CalculationResult.fromJson({
        'id': 'abc',
        'calculation_type': 'bearing_capacity',
        'method': 'terzaghi',
        'status': 'CALCULATED',
        'preliminary': true,
        'engine_version': '0.1.0',
        'standard': 'kebs',
        'results': {
          'ultimate_capacity_kpa': 986.9,
          'net_allowable_capacity_kpa': 319.9,
        },
        'warnings': [
          {'severity': 'WARNING', 'code': 'PRELIMINARY_RESULT', 'message': 'Correlated.'},
        ],
      });
      expect(result.isRefusal, isFalse);
      expect(result.ultimateKpa, closeTo(986.9, 0.01));
      expect(result.netAllowableKpa, closeTo(319.9, 0.01));
      expect(result.preliminary, isTrue);
      expect(result.warnings.single.severity, 'WARNING');
    });

    test('a refusal is a result, not an error', () {
      final result = CalculationResult.fromJson({
        'calculation_type': 'bearing_capacity',
        'method': 'vesic',
        'status': 'INSUFFICIENT_DATA',
        'results': {},
        'warnings': [
          {
            'severity': 'CRITICAL',
            'code': 'MISSING_REQUIRED_INPUT',
            'message': 'friction_angle_deg is required.',
          },
        ],
      });
      expect(result.isRefusal, isTrue);
      expect(result.warnings.single.isCritical, isTrue);
      expect(result.netAllowableKpa, isNull);
    });

    test('a soil layer keeps its provenance and knows if it was measured', () {
      final measured = SoilLayer.fromJson({
        'id': '1', 'top_depth_m': 0.3, 'bottom_depth_m': 2.5,
        'classification_source': 'LABORATORY', 'uscs_class': 'CH',
      });
      final seen = SoilLayer.fromJson({
        'id': '2', 'top_depth_m': 2.5, 'bottom_depth_m': 4.0,
        'classification_source': 'AI', 'confidence': 0.81,
      });
      expect(measured.isMeasured, isTrue);
      expect(measured.thicknessM, closeTo(2.2, 0.001));
      expect(seen.isMeasured, isFalse, reason: 'an AI class is not a measurement');
      expect(seen.confidence, 0.81);
    });

    test('a candidate carries its criteria and its construction steps', () {
      final candidate = FoundationCandidate.fromJson({
        'foundation_type': 'strip',
        'label': 'Strip footing',
        'status': 'CANDIDATE_WITH_CONDITIONS',
        'relative_cost': 'low',
        'criteria': [
          {'name': 'Bearing capacity', 'verdict': 'PASS', 'evidence': '65% of allowable'},
          {'name': 'Ground conditions', 'verdict': 'FAIL', 'evidence': 'Expansive clay'},
        ],
        'rationale': ['Simplest option where the ground allows it'],
        'conditions': ['Viable once the expansive clay is removed'],
        'missing_data': [],
        'construction_steps': [
          {
            'order': 1,
            'title': 'Remove or isolate the expansive clay',
            'detail': 'Excavate it out.',
            'hold_point': true,
            'verify': 'Trial pit records across the footprint.',
            'triggered_by': 'Expansive clay identified in the investigation',
          },
          {'order': 2, 'title': 'Set out', 'detail': '...', 'hold_point': false},
        ],
      });
      expect(candidate.failures, 1);
      expect(candidate.statusLabel, 'Candidate, with conditions');
      expect(candidate.steps.first.holdPoint, isTrue);
      expect(candidate.steps.first.triggeredBy, contains('Expansive clay'));
      expect(candidate.steps.last.holdPoint, isFalse);
    });

    test('an engineer account can approve and an ordinary one cannot', () {
      expect(
        Account.fromJson({'id': '1', 'email': 'a@b.c', 'role': 'engineer'}).canApprove,
        isTrue,
      );
      expect(
        Account.fromJson({'id': '2', 'email': 'd@e.f', 'role': 'free'}).canApprove,
        isFalse,
      );
    });

    test('a project without a location does not render an empty comma', () {
      final project = Project.fromJson({
        'id': '1', 'name': 'Site', 'updated_at': '2026-09-22T10:00:00Z',
      });
      expect(project.location, isEmpty);

      final located = Project.fromJson({
        'id': '2', 'name': 'Site', 'country': 'Kenya',
        'administrative_area': 'Machakos County',
        'updated_at': '2026-09-22T10:00:00Z',
      });
      expect(located.location, 'Machakos County, Kenya');
    });
  });
}
